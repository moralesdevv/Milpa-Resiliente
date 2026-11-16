# ADR-013: Docker Compose, imágenes y modo demo

- **Fecha:** 2026-11-14 · **Estado:** aceptado

## Decisión
- **Dos servicios**: `db` (`postgis/postgis:16-3.4` + script de inicialización del rol de aplicación) y `app` (API + worker en proceso + estáticos de R4 si existen). Sin tercer servicio ni cola. La DB **no publica puertos**.
- `Dockerfile.app` multi-etapa (`deps → runtime | test`): Python 3.12-slim, Pango/HarfBuzz/Fontconfig/fuentes, uv fijado (0.13.8), `uv sync --frozen`, usuario `10001` sin privilegios, `cap_drop: ALL`, `no-new-privileges`, healthcheck sobre `/healthz`. Sin secretos en capas: todo por entorno en ejecución (`POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, `JWT_SECRET` son obligatorias en Compose).
- **Migraciones:** el entrypoint ejecuta `alembic upgrade head` con `MIGRATION_DATABASE_URL` (rol propietario) y la **elimina del entorno** antes de lanzar uvicorn; la API corre con el rol `milpa_app` (sin BYPASSRLS). Alternativa descartada: servicio `migrate` aparte (contradice «dos servicios»).
- Un único proceso uvicorn: el pool de trabajos y el limitador de tasa son por proceso; escalar horizontalmente exigiría un ADR (sin Redis).
- **Demo:** `DEMO_READONLY=true` bloquea toda escritura salvo login; `make demo` exige `data/demo/EXPECTED.json` (R1) y falla claramente si no existe — no se fabrican datos.
- Los tests completos se ejecutan en la etapa `test` (`make test-docker`) contra un PostGIS efímero.

## Riesgos
Imagen con bibliotecas nativas (tamaño); verificación periódica con `pip-audit` y actualización de la imagen base. **Aprobador:** R3.
