# Despliegue y entorno (BE-09)

> **Actualización 2026-11-16:** variables nuevas: `DEMO_PUBLIC_ACCESS` (sesión pública de demo, por defecto `false`; si `true` el entrypoint crea la cuenta sin contraseña con `create-demo-user`), `DEMO_USER_EMAIL`, `DEMO_TTL_MINUTES`, `CORE_REGION_PATH`, `CORE_STRATEGIES_PATH`, `CORE_CATALOGS_DIR`. El entrypoint ejecuta `register-engine` tras las migraciones. La imagen incluye `milpa-core` (construcción aún sin verificar en este equipo).

## Requisitos
Docker + Docker Compose v2. Para desarrollo local sin Docker: Python 3.12 + `uv` + un PostgreSQL 16/PostGIS (ver §3). El PDF se genera con ReportLab (Python puro, ADR-021): **no** requiere Docker ni Pango, tampoco en Windows nativo. PostgreSQL 16 + PostGIS sí es requisito (la API lo necesita; no es el PDF). `scripts/start_local.ps1` usa `DATABASE_URL` si está definida; solo si falta intenta el contenedor de desarrollo.

## 0. Publicar la demo como sitio web (hackatón)
Un solo contenedor sirve la API **y** la SPA (`/`), más PostgreSQL/PostGIS. Pasos:
```bash
cp .env.example .env
#   POSTGRES_PASSWORD, APP_DB_PASSWORD (distintas), JWT_SECRET (>= 32 caracteres, python -c "import secrets; print(secrets.token_urlsafe(48))")
#   DEMO_PUBLIC_ACCESS=true     # LAUNCH DEMO entra sin login (alcance limitado, ADR-019)
#   MILPA_MODE=sandbox          # los parámetros agronómicos siguen provisionales (evidencia C)
#   CORS_ORIGINS=https://su-dominio     # si el front se sirve desde otro origen
docker compose up --build -d
```
Al primer arranque, con `DEMO_PUBLIC_ACCESS=true` (o `BOOTSTRAP_DEMO=true`), `entrypoint.sh` migra, registra el catálogo del motor y la
cuenta demo, y ejecuta `infra/scripts/bootstrap-demo.sh` (idempotente): copia los datos **reales** ya curados de `camotan_jocotan`
(NASA POWER + GPM IMERG), registra manifiesto, zona, procedencia y elevación/pendiente del DEM Copernicus GLO-30. No descarga nada.
- Cualquier PaaS con Docker + PostgreSQL con PostGIS (Render, Railway, Fly.io…) sirve: construya `infra/Dockerfile.app` (destino `runtime`),
  defina las mismas variables (`DATABASE_URL` del rol sin privilegios, `MIGRATION_DATABASE_URL` del propietario solo para el arranque) y exponga el puerto 8000. Compruebe `/healthz`.
- Con PostgreSQL gestionado (p. ej. Neon): cree antes el rol `milpa_app` (`NOSUPERUSER NOBYPASSRLS`) y la extensión `postgis`; las dos URL
  llevan `?sslmode=require`. Detrás del proxy del PaaS defina `TRUST_FORWARDED_FOR=true` (si no, todos los visitantes comparten la IP del proxy
  y el límite por IP se agota) y suba `RATE_LIMIT_PER_MIN` (p. ej. 600: el límite cuenta también los estáticos de la SPA). El cálculo corre en un
  proceso aparte y necesita memoria libre suficiente; con instancias muy pequeñas fije `OPENBLAS_NUM_THREADS=1`.
- El token **EARTHDATA_TOKEN no es necesario** para la demo (los datos IMERG ya están curados y no se redistribuyen en bruto); las ingestas nuevas sí lo necesitan.
- Las teselas del mapa vienen de CARTO (datos de OpenStreetMap, con atribución); para otro proveedor defina `VITE_MAP_TILE_URL`/`VITE_MAP_ATTRIBUTION` al construir.
- Estado de verificación: ver `docs/FINAL_PROJECT_AUDIT.md` (la construcción de la imagen se anota ahí con su resultado real).

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
