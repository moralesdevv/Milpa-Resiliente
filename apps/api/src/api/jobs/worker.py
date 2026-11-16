"""Ejecución de un trabajo dentro de un proceso worker.

Cada proceso crea su propio Engine/Session (nunca compartidos). El handler corre con
``SET LOCAL app.user_id`` = creador del trabajo, de modo que RLS limita lo que puede tocar.
Los errores se persisten tipados y SIN datos sensibles (solo código, clase y mensaje seguro).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from api.db.engine import get_engine
from api.db.uow import UnitOfWork
from api.errors import ApiError
from api.jobs.context import JobCancelled, JobContext, JobTimedOut, RetryableJobError
from api.jobs.dispatch import WorkerConfig
from api.jobs.registry import get_handler
from api.repositories.jobs import JobRepository
from api.storage.object_store import LocalObjectStore

log = logging.getLogger("api.jobs")

SAFE_INTERNAL_MESSAGE = "El trabajo falló por un error interno. Consulte los registros técnicos."


def error_payload(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, ApiError):
        return {"code": str(exc.code), "type": type(exc).__name__, "message": exc.detail}
    if isinstance(exc, JobTimedOut):
        return {
            "code": "JOB_TIMEOUT",
            "type": "JobTimedOut",
            "message": "Se superó el tiempo máximo",
        }
    return {"code": "JOB_FAILED", "type": type(exc).__name__, "message": SAFE_INTERNAL_MESSAGE}


def run_job(job_id: UUID, cfg: WorkerConfig) -> None:
    engine = get_engine(cfg.database_url)
    store = LocalObjectStore(Path(cfg.data_dir))
    while True:
        with Session(engine) as s:
            job = JobRepository(s).claim(job_id)
            if job is None:
                s.rollback()
                return  # ya tomado, cancelado o inexistente: idempotente
            kind, payload, created_by, attempt = (
                job.kind,
                dict(job.payload),
                job.created_by,
                job.attempts,
            )
            s.commit()

        handler = get_handler(kind)
        outcome: tuple[str, dict[str, Any]] | None = None
        retry = False
        with UnitOfWork(engine) as uow:
            if created_by is not None:
                uow.set_user(created_by)
            ctx = JobContext(
                job_id=job_id,
                kind=kind,
                created_by=created_by,
                attempt=attempt,
                uow=uow,
                engine=engine,
                store=store,
                timeout_seconds=cfg.timeout_seconds,
            )
            try:
                if handler is None:
                    raise RuntimeError(f"Sin handler para el tipo de trabajo {kind!r}")
                result = handler(ctx, payload)
                outcome = ("ok", result)
            except JobCancelled:
                log.info("job_cancelled", extra={"job_id": str(job_id)})
                return
            except RetryableJobError as exc:
                uow.rollback()
                retry = attempt < cfg.max_attempts
                outcome = ("failed", error_payload(exc))
            except Exception as exc:
                uow.rollback()
                outcome = ("failed", error_payload(exc))
                log.error(
                    "job_failed", extra={"job_id": str(job_id), "exc_type": type(exc).__name__}
                )

        with Session(engine) as s:
            repo = JobRepository(s)
            if retry:
                repo.requeue(job_id, error=outcome[1] if outcome else None)
            elif outcome and outcome[0] == "ok":
                repo.finish_ok(job_id, outcome[1])
            elif outcome:
                repo.finish_failed(job_id, outcome[1])
            s.commit()
        if not retry:
            return
        time.sleep(min(0.2 * 2**attempt, 5.0))  # backoff exponencial acotado
