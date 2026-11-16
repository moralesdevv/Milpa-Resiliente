# ADR-016: Límites, timeouts y recuperación de trabajos

- **Fecha:** 2026-11-14 · **Estado:** **propuesto** (valores operativos pendientes)

## Decisión
- Concurrencia: `JOB_MAX_WORKERS` (por defecto 2; la spec estima 1–2, **a medir** en BE-11).
- Intentos: `JOB_MAX_ATTEMPTS=3`. Reintento automático solo para `RetryableJobError` y para huérfanos idempotentes.
- Timeout: `JOB_TIMEOUT_SECONDS=0` (desactivado). Existe el mecanismo (timeout blando comprobado en `check_cancelled`) pero **no se asume un valor** sin decisión por tipo de trabajo. Un `ProcessPoolExecutor` no puede interrumpir código nativo bloqueado; un timeout duro exigiría procesos dedicados (nuevo ADR con medición).
- Recuperación al arrancar (`recover_jobs`): huérfanos y `queued` se redespachan según `IDEMPOTENT_KINDS`.
- Límites HTTP: JSON ≤ 1 MiB; CSV ≤ `MAX_UPLOAD_MB` (2) en streaming; filas ≤ 5000 y columnas ≤ 64; `limit` de listas ≤ `PAGE_MAX_LIMIT` (100); tasa `RATE_LIMIT_PER_MIN` (120) por IP y usuario.
- Todos configurables; los valores por defecto son **provisionales** y no se presentan como objetivos medidos.

**Aprobadores:** R3 tras benchmarks (BE-11).
