# ADR-007: Trabajos con `engine.job` + `concurrent.futures`

- **Fecha:** 2026-11-14 · **Estado:** aceptado (mecanismo); **propuesto — requiere aprobación** (tipos `parcel_delete` y `consent_purge`, C4)

## Contexto
Los trabajos pesados no pueden bloquear HTTP; no se admiten Redis/Celery/ARQ. Estados: `queued|running|ok|failed|cancelled`. Tipos de la spec: `zone_ingest|analysis_run|scenario_run|report`.

## Decisión
- Estado en `engine.job` (PostgreSQL). `ProcessPoolExecutor` con contexto `spawn` en el proceso `app`; al worker viajan solo `job_id` + `WorkerConfig` (sin secretos JWT); cada proceso crea su propio Engine/Session (`get_engine` cachea por `(pid,url)`).
- Registro del job **antes** de despachar; `202 + Location`. `Idempotency-Key` con alcance por usuario (`<user_id>:<clave>`): misma clave+operación → mismo job; misma clave y operación distinta → 409.
- Transiciones atómicas (`UPDATE … WHERE status=…`): `claim` es exclusivo (probado con 6 hilos), un job cancelado no «resucita».
- Cancelación: `queued` inmediata; `running` cooperativa (`ctx.check_cancelled()`), resultado descartado.
- Reintentos: `RetryableJobError` (hasta `JOB_MAX_ATTEMPTS`, backoff acotado). Recuperación al arrancar: `running` huérfano idempotente → `queued`; no idempotente o sin intentos → `failed` (`ORPHANED`).
- Errores persistidos como `{code,type,message}` **sin texto de excepción** (puede contener datos privados).
- **Extensión C4:** `parcel_delete` y `consent_purge` se añaden al CHECK de `engine.job.kind`.

## Alternativas
Hilos (no aíslan CPU), cola externa (descartada), tabla + `LISTEN/NOTIFY` (innecesario).

## Consecuencias / riesgos
(+) Sin infraestructura nueva; reinicio seguro. (−) Un `running` real puede reencolarse tras un reinicio y repetir trabajo → por eso solo los tipos idempotentes se reencolan (`registry.IDEMPOTENT_KINDS`; `zone_ingest` NO, hasta que R1 confirme). Timeouts/reintentos por tipo: pendientes (DP); `JOB_TIMEOUT_SECONDS=0` = sin timeout.

**Aprobadores:** R3; R1 (idempotencia de `zone_ingest`); R2 (de `analysis_run`).
