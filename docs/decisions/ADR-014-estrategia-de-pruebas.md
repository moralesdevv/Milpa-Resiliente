# ADR-014: Estrategia de pruebas

- **Fecha:** 2026-11-14 · **Estado:** aceptado

## Decisión
- Niveles: unitarias y de propiedades (`apps/api/tests`, Hypothesis), integración y seguridad (`tests/integration`, `tests/privacy`) con **PostgreSQL 16 + PostGIS real** y el **rol real de aplicación** (RLS efectiva), contrato (`tests/contract`: OpenAPI, paridad de enums, límites arquitectónicos, Schemathesis).
- Base efímera por sesión (`milpa_test_<id>`), migrada con Alembic desde cero y limpiada entre pruebas; fábricas con datos **sintéticos de prueba** (`testkit/`).
- Dobles de prueba etiquetados (`testkit/doubles.py`); nunca importados por `src/`.
- `pypdf` (solo desarrollo) para extraer texto de PDFs en las pruebas de privacidad.
- Regla: una prueba omitida **no** es una prueba aprobada; las omisiones llevan motivo (sin Pango en el host, symlinks no permitidos, tipos TS pendientes de R4). El resultado se informa como aprobado / fallido / omitido / bloqueado.
- CI: lint, mypy estricto, snapshot OpenAPI, pytest completo, `pip-audit`, escaneo de secretos, build de imágenes y arranque de Compose.
- Fuera de alcance de R3: `T-P` y `T-G` científicas (R2), `T-UI`/`T-A` (R4).

## Riesgos
Dependencia de Docker para PDF y para PostgreSQL local. **Aprobador:** R3.
