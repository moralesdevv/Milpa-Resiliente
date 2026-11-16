# Sistema de trabajos (BE-04)

> **Actualización 2026-11-16:** los handlers `analysis_run`, `scenario_run` y `report` ya persisten resultados reales (ver `jobs/handlers/engine_jobs.py` y `reports.py`); `zone_ingest` sigue dependiendo de `ETL_INGEST_ENABLED`.

`engine.job` (PostgreSQL) + `concurrent.futures.ProcessPoolExecutor` dentro del proceso `app`. Sin Redis/Celery/ARQ (ADR-007).

## Tipos, estados y campos
| Tipo | Quién lo crea | Handler | Idempotente (reencolable tras reinicio) | Dependencia |
|---|---|---|---|---|
| `zone_ingest` | `POST /zones` | `IngestPort` (R1) | **no** | R1 |
| `analysis_run` | `POST /zones/{id}/runs` | `EnginePort.run_base_analysis` | sí | R2 |
| `scenario_run` | `POST /runs/{id}/scenarios` | `EnginePort.run_scenarios` | sí | R2 |
| `report` | `POST /reports` | `EnginePort.build_report` → PDF | sí | R2/R4 |
| `parcel_delete` | `DELETE /parcels/{id}` | borrado integral (real) | sí | — |
| `consent_purge` | retirar consentimiento | limpieza por propósito (real) | sí | — |
`parcel_delete` y `consent_purge` son **extensión R3** (ADR-007, pendiente de aprobación).
Estados: `queued → running → ok | failed | cancelled`. Campos: `job_id, kind, status, progress, payload, result, error, idempotency_key, attempts, created_by, created_at, started_at, finished_at`. `payload`/`result` llevan `"v": 1` (versión de esquema).

## Flujo
1. El servicio crea el registro (`queued`) y hace `commit` **antes** de despachar; responde `202 + Location`.
2. `ProcessPoolDispatcher.submit(job_id)` → proceso `spawn` → `run_job`: `claim` atómico (`UPDATE … WHERE status='queued'`), abre su propio Engine/Session, fija `SET LOCAL app.user_id = created_by` (RLS aplica al handler), ejecuta, y cierra con `finish_ok/finish_failed` (`WHERE status='running'`: un job cancelado no se reescribe).
3. Al worker solo viajan `job_id` + `WorkerConfig` (BD, `DATA_DIR`, intentos, timeout); nunca `JWT_SECRET` ni objetos de sesión.
4. El progreso (`ctx.progress`) y los *checkpoints* se escriben en transacciones propias (sobreviven a un `rollback` del handler).

## Idempotencia
`Idempotency-Key` (1–128 caracteres `[A-Za-z0-9._:-]`) se guarda como `<user_id>:<clave>`: misma clave + mismo usuario + misma operación ⇒ el trabajo existente (`202`); otra operación ⇒ `409 IDEMPOTENCY_CONFLICT`; otro usuario ⇒ trabajo independiente (sin fuga entre cuentas). `POST /zones` reconoce el reintento antes de crear otra zona.

## Cancelación
`DELETE /v1/jobs/{id}`: `queued` → `cancelled` inmediato (el worker, al reclamar, no ejecuta). `running` → `cancelled` cooperativo: el handler lo detecta en `ctx.check_cancelled()` y abandona; **su resultado se descarta**. Un handler que nunca consulta no se interrumpe (un pool de procesos no puede matar código bloqueado). Terminado ⇒ no cambia.

## Reintentos y errores
`RetryableJobError` ⇒ hasta `JOB_MAX_ATTEMPTS` (3) con espera exponencial acotada. Un error de handler ⇒ `failed` con `error = {code,type,message}`: para `ApiError` el código y el texto seguro (p. ej. `DEPENDENCY_NOT_INTEGRATED`); para cualquier otra excepción solo el nombre de la clase y un mensaje fijo — **nunca** `str(exc)` (puede contener datos privados).

## Recuperación tras reinicio
Al arrancar (`lifespan`): `running` huérfano ⇒ `queued` (error `ORPHANED_REQUEUED`) si el tipo es idempotente y `attempts < max`; si no ⇒ `failed` (`ORPHANED`). Luego se redespachan todos los `queued`. Probado: `test_orphan_recovery_*`, `test_app_startup_runs_recovery`.

## Borrado de parcela (detalle)
(1) lista archivos (`results/<run_id>`, PDFs) y guarda un checkpoint en `engine.job.result`; (2) borra filas en una transacción con el contexto del dueño; (3) borra archivos. Si el proceso cae entre (2) y (3), la re-ejecución completa los archivos desde el checkpoint.

## Parámetros (`.env`)
`JOB_MAX_WORKERS` (2) · `JOB_MAX_ATTEMPTS` (3) · `JOB_TIMEOUT_SECONDS` (0 = sin timeout; política por tipo **pendiente**).

## Inspección
```sql
SELECT job_id, kind, status, progress, attempts, error->>'code' AS error_code, created_at
FROM engine.job ORDER BY created_at DESC LIMIT 20;      -- con el rol propietario
```
```bash
curl -s :8000/v1/jobs/<id> -H "Authorization: Bearer $T"   # creador o admin
```

## Medición
`docs/benchmarks/LATEST.md`: sobrecarga de un trabajo nulo (en línea) y de 12 trabajos en pool de 1 y 2 workers (incluye el arranque `spawn`). No se fijan objetivos.
