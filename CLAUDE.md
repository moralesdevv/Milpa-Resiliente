# MILPA - Backend Engineering Rules
## Documentos de referencia obligatorios

Antes de realizar cualquier modificación:

1. Leer CLAUDE.MD.
2. Leer Especificacion_Tecnica_MILPA_R3.md.
3. Inspeccionar README.md.
4. Inspeccionar la arquitectura existente.

La especificación técnica de R3 define el alcance
y los requisitos de implementación del backend.

No ignorar ni omitir requisitos de la especificación.
## 1. Core Stack
- Python 3.12
- FastAPI
- Pydantic v2
- PostgreSQL 16 + PostGIS
- SQLAlchemy 2
- Alembic
- uv for dependency management

## 2. Architecture
- Follow the existing project architecture.
- Keep routers, services, repositories and schemas separated.
- Never duplicate scientific logic from milpa_core.
- The backend must not import milpa_etl.
- Consume curated datasets produced by the ETL.

## 3. Strict Restrictions
- Do not introduce Redis, Celery, ARQ or Dask.
- Do not introduce new infrastructure without an ADR.
- Do not replace existing technologies without approval.
- Do not modify unrelated modules.
- Do not invent API contracts.

## 4. Security
- Enforce authorization on every protected resource.
- Respect PostgreSQL Row-Level Security.
- Use SET LOCAL app.user_id within the correct transaction.
- Never expose private coordinates or sensitive information.
- Never log tokens, passwords or sensitive request bodies.
- Validate all external inputs.

## 5. Scientific Reproducibility
- Preserve SHA-256 provenance hashes.
- Never modify scientific calculations inside the API.
- Preserve deterministic report generation.
- Keep data lineage traceable.

## 6. Code Quality
- Use Ruff.
- Use strict mypy in milpa_core.
- Write pytest tests.
- Use Hypothesis for property-based testing.
- Validate API contracts with Schemathesis.

## 7. Development Workflow
Before implementing:
1. Inspect the existing architecture.
2. Identify affected modules.
3. Explain the proposed implementation.
4. Identify required tests.

After implementing:
1. Run relevant tests.
2. Run Ruff.
3. Check types.
4. Report modified files.
5. Report any unresolved issues.

Never claim tests passed unless they were actually executed.
