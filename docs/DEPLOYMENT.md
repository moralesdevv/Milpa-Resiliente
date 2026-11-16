# Despliegue y entorno (BE-09)

## Requisitos
Docker + Docker Compose v2. Para desarrollo local sin Docker: Python 3.12 + `uv` + un PostgreSQL 16/PostGIS (ver §3). Windows nativo **no** puede generar PDF (WeasyPrint necesita Pango): use la imagen.

## 1. Arranque con Compose (dos servicios: `db`, `app`)
```bash
cp .env.example .env
# edite .env: POSTGRES_PASSWORD, APP_DB_PASSWORD (distintas) y JWT_SECRET (>= 32 caracteres)
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build -d       # = make up
curl -s http://127.0.0.1:8000/healthz        # {"status":"ok","db":"ok"}
```
- `db`: `postgis/postgis:16-3.4`; crea el rol `milpa_app` (`NOSUPERUSER NOBYPASSRLS`) en el primer arranque; sin puertos publicados; volumen `pgdata`.
- `app`: ejecuta `alembic upgrade head` con el rol propietario (`MIGRATION_DATABASE_URL`), **elimina esa variable del entorno** y arranca uvicorn (un proceso) con el rol `milpa_app`; usuario `10001`; volumen `data` en `/data`; healthcheck `/healthz`; publica `127.0.0.1:8000` (`APP_PUBLISH`).
- Con `RUN_MIGRATIONS=false` las migraciones se omiten (p. ej. tras migrar por otra vía).

## 2. Primer usuario (no hay registro público) — comando verificado
```bash
docker compose exec -T -e NEW_USER_PASSWORD='<contraseña de 12+ caracteres>' app   python -m api.cli create-user --email tecnico@example.org --role tecnico
```
La CLI usa `MIGRATION_DATABASE_URL` (rol propietario), que está en la *configuración* del contenedor aunque se elimina del entorno del proceso uvicorn (ver `docs/SECURITY.md §6`).
Comprobado con `docker compose up` real: `/healthz` 200, rol `milpa_app` sin superusuario/BYPASSRLS, 48 tablas, revisión `0013`, proceso `uid 10001`, BD sin puertos publicados, login funcional y persistente tras `restart`, `report-sample` genera PDF (mismo SHA-256 en dos contenedores distintos).

## 3. Desarrollo local con uv
```bash
make setup                       # uv sync --frozen --all-packages --all-groups
export DATABASE_URL=postgresql+psycopg://milpa_app:<pw>@127.0.0.1:5432/milpa
export MIGRATION_DATABASE_URL=postgresql+psycopg://milpa_owner:<pw>@127.0.0.1:5432/milpa
export JWT_SECRET=<>=32 caracteres>
make db-migrate
uv run --all-packages uvicorn api.main:app --reload --no-access-log
# OpenAPI: http://127.0.0.1:8000/docs   |   make openapi  -> docs/openapi/openapi.json
```
El rol `milpa_app` debe existir antes de migrar (ver `infra/db/initdb/10-roles.sh`).

## 4. Variables
Ver `.env.example` (todas documentadas). La aplicación **falla al arrancar** si falta `DATABASE_URL`/`JWT_SECRET`, si el secreto tiene <32 caracteres o (en `production`) parece de ejemplo, si `CORS_ORIGINS` contiene `*` o si `ENABLE_EXACT_GEOMETRY=true`.

## 5. Modo demostración
`DEMO_READONLY=true` ⇒ solo lectura (salvo login) y sin acceso a APIs externas. `make demo` **exige** `data/demo/EXPECTED.json` (paquete de R1); sin él falla indicando qué falta. Con la infraestructura sola se puede arrancar en modo técnico (`make up`).

## 6. Imágenes y verificación
`make build` · `make test-docker` (suite completa en la etapa `test` contra un PostGIS efímero) · CI verifica build + arranque + `/healthz` + rol sin BYPASSRLS + usuario no root.

## 7. Operación
- Copias de seguridad/retención: **pendiente de política** (DP-13); no use datos personales reales hasta aprobarla.
- Un solo proceso: no escale réplicas sin ADR (limitador y pool son por proceso).
- Detener sin perder datos: `docker compose stop`; borrar volúmenes (`down -v`) elimina la base y los archivos.
