# syntax=docker/dockerfile:1.7
# Imagen de la aplicación (API + worker en proceso + estáticos de R4 cuando existan).
# Incluye las bibliotecas nativas de WeasyPrint (Pango/HarfBuzz/Fontconfig) y fuentes.
# Etapas: runtime (por defecto, sin dependencias de desarrollo) y test (pytest/ruff/mypy).

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 libfontconfig1 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
# uv fijado (la versión coincide con la usada para generar uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/
WORKDIR /srv/milpa

# --- dependencias (capa cacheable) -------------------------------------------------------------
FROM base AS deps
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/milpa_etl/pyproject.toml packages/milpa_etl/pyproject.toml
COPY packages/milpa_core/pyproject.toml packages/milpa_core/pyproject.toml
RUN uv sync --frozen --no-dev --package milpa-api --package milpa-etl --package milpa-core --no-install-workspace

# --- runtime ------------------------------------------------------------------------------------
FROM deps AS runtime
COPY apps/api/src apps/api/src
COPY apps/api/migrations apps/api/migrations
COPY apps/api/templates apps/api/templates
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY packages/milpa_etl/src packages/milpa_etl/src
COPY packages/milpa_core/src packages/milpa_core/src
COPY catalogs catalogs
COPY regions regions
# paquete de demostración congelado (sintético, rotulado): se copia a DATA_DIR/demo si falta
COPY data/demo /opt/milpa/demo
COPY README.md ./
RUN uv sync --frozen --no-dev --package milpa-api --package milpa-etl --package milpa-core
COPY infra/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
 && groupadd --system --gid 10001 milpa \
 && useradd --system --uid 10001 --gid milpa --home-dir /srv/milpa --shell /usr/sbin/nologin milpa \
 && mkdir -p /data && chown -R milpa:milpa /data
ENV DATA_DIR=/data \
    XDG_CACHE_HOME=/tmp/.cache
USER milpa
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# Un único proceso: el ProcessPoolExecutor de trabajos y el limitador de tasa viven en él (ADR-007/013).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]

# --- test (solo CI/desarrollo): incluye dependencias de desarrollo y las pruebas -----------------
FROM deps AS test
COPY apps/api/src apps/api/src
COPY apps/api/migrations apps/api/migrations
COPY apps/api/templates apps/api/templates
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/tests apps/api/tests
COPY packages packages
COPY catalogs catalogs
COPY regions regions
COPY data/demo data/demo
COPY tests tests
COPY testkit testkit
COPY docs/openapi docs/openapi
COPY references references
COPY infra infra
COPY conftest.py README.md docker-compose.yml .env.example ./
RUN uv sync --frozen --all-groups --package milpa-api --package milpa-etl --package milpa-core
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
