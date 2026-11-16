# Registro de decisiones de arquitectura (ADR) — R3

Estados: `propuesto`, `aceptado`, `rechazado`, `reemplazado`. Una decisión que cambie una tecnología obligatoria, un contrato compartido o una frontera entre componentes **queda pendiente de aprobación** y no se aplica en silencio.

| ADR | Título | Estado |
|---|---|---|
| [001](ADR-001-monolito-modular.md) | Monolito modular y límites | aceptado (ruta `docs/decisions/` propuesta) |
| [002](ADR-002-fastapi-sqlalchemy-alembic.md) | FastAPI / SQLAlchemy / Alembic y driver | aceptado; driver propuesto |
| [003](ADR-003-esquemas-y-propiedad-de-migraciones.md) | Esquemas y propiedad de migraciones | **propuesto (R1+R3)** |
| [004](ADR-004-postgis.md) | PostGIS y generalización | aceptado; método propuesto |
| [005](ADR-005-autenticacion-jwt-argon2id.md) | JWT + Argon2id | aceptado; valores propuestos |
| [006](ADR-006-rbac-rls-contexto-app-user-id.md) | RBAC + RLS y `app.user_id` | aceptado |
| [007](ADR-007-trabajos-concurrent-futures.md) | Trabajos con `concurrent.futures` | aceptado; tipos nuevos **propuestos** |
| [008](ADR-008-parquet-y-almacenamiento-local.md) | Parquet y almacenamiento local | aceptado; contratos pendientes (R1) |
| [009](ADR-009-integracion-milpa-core.md) | Integración con `milpa_core` | **propuesto (R2)** |
| [010](ADR-010-openapi-y-contratos.md) | OpenAPI, contratos, errores y mock | **propuesto** |
| [011](ADR-011-jinja2-weasyprint-seguridad.md) | Jinja2/WeasyPrint y seguridad | aceptado |
| [012](ADR-012-hashes-reproducibilidad.md) | Hashes y reproducibilidad | aceptado; reproducción bloqueada (R1/R2) |
| [013](ADR-013-docker-compose.md) | Docker Compose y modo demo | aceptado |
| [014](ADR-014-estrategia-de-pruebas.md) | Estrategia de pruebas | aceptado |
| [015](ADR-015-privacidad-consentimiento-retencion.md) | Privacidad, consentimiento, retención | **propuesto (DP-13)** |
| [016](ADR-016-limites-timeouts-recuperacion.md) | Límites, timeouts, recuperación | **propuesto** |
| [017](ADR-017-alineacion-contratos-auditoria-integracion.md) | Alineación de contratos y defensas de integración (auditoría) | **propuesto** |
| [018](ADR-018-integracion-de-r1-y-r4-en-la-raiz.md) | Integración de R1 y R4 (`references/`) en la raíz | **propuesto** |
| [019](ADR-019-sesion-publica-de-demostracion.md) | Sesión pública de demostración | **propuesto** |
| [020](ADR-020-integracion-de-milpa-core.md) | Integración de `milpa_core` (R2) | **propuesto** |
| [021](ADR-021-reportlab-motor-pdf.md) | ReportLab como motor PDF (WeasyPrint opcional) | **propuesto** |
| [022](ADR-022-limite-municipal-y-seleccion-de-ubicacion.md) | Límite municipal y selección de ubicación | **propuesto** |
| [023](ADR-023-validacion-agronomica-jocotan.md) | Validación agronómica de Jocotán (JSON, inicio de lluvias sandbox, estación) | **propuesto** |

Plantilla: ver cualquiera de los anteriores (fecha, estado, contexto/problema, restricciones, alternativas, decisión, justificación, consecuencias, riesgos, módulos afectados, aprobadores, relación con otros ADR).
