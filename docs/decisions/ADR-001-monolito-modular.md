# ADR-001: Monolito modular y límites de componentes

- **Fecha:** 2026-11-14 · **Estado:** aceptado (decisión de la especificación) · propuesto: ruta `docs/decisions/` (ver C1)
- **Relación:** base de ADR-002…016

## Contexto y problema
MILPA se reparte entre R1 (datos), R2 (motor), R3 (backend) y R4 (frontend). Hay que fijar cómo se organiza R3 y qué fronteras no se cruzan.

## Restricciones
Especificación R3 §2–§4 y `CLAUDE.md`: monolito modular, sin microservicios; `milpa_core` no depende de la API; la API no importa `milpa_etl`; ningún cálculo científico en la API; sin Redis/Celery/ARQ/Dask/MinIO.

## Alternativas
1. Microservicios (API, worker, informes) — rechazada: sobredimensionada para 1–2 trabajos concurrentes.
2. Monolito sin capas — rechazada: mezcla autorización, persistencia y contratos.
3. **Monolito modular por capas (elegida).**

## Decisión
Un paquete `apps/api/src/api` con capas `routers → services → repositories → models`, más `schemas`, `security`, `jobs`, `reports`, `adapters`, `storage`, `db`, `config`. Los routers solo validan, delegan y construyen respuestas. Dos contenedores: `db` y `app`.

## Justificación y consecuencias
(+) Fronteras comprobables: `tests/contract/test_boundaries.py` falla si un router importa SQLAlchemy/repositorios, si la API importa `milpa_etl` o si algo fuera de `adapters/milpa_core.py` referencia `milpa_core`. (−) Un solo proceso: el limitador de tasa y el pool de trabajos viven en él (ver ADR-013).

## Riesgos
Crecimiento de `services/`. Mitigación: un servicio por agregado y revisión en PR.

## Conflicto C1 (ruta de ADR)
El README integral usa `docs/adr/`; la especificación R3 y el encargo usan `docs/decisions/`. **R3 usa `docs/decisions/`**. Pendiente de confirmación del equipo (cambiar solo la ruta, no el contenido).

## Módulos afectados
Todo `apps/api`. **Aprobadores:** líder de R3 + R2 (frontera `milpa_core`).
