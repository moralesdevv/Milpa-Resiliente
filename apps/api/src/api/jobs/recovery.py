"""Recuperación al arrancar (spec R3 §13.5): reencolar huérfanos idempotentes o marcarlos fallidos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine, func, update
from sqlalchemy.orm import Session

from api.jobs.dispatch import JobDispatcher
from api.jobs.registry import IDEMPOTENT_KINDS
from api.models.engine import Job
from api.models.enums import JobKind, JobStatus
from api.repositories.jobs import JobRepository

log = logging.getLogger("api.jobs")


@dataclass(frozen=True)
class RecoveryReport:
    requeued: int
    failed: int
    redispatched: int


def recover_jobs(engine: Engine, dispatcher: JobDispatcher, *, max_attempts: int) -> RecoveryReport:
    requeued = failed = 0
    to_dispatch = []
    with Session(engine) as s:
        repo = JobRepository(s)
        for job in repo.with_status(JobStatus.running):
            # Un job 'running' al arrancar es huérfano: el proceso que lo ejecutaba ya no existe.
            kind = JobKind(job.kind)
            if kind in IDEMPOTENT_KINDS and job.attempts < max_attempts:
                repo.requeue(
                    job.job_id,
                    error={"code": "ORPHANED_REQUEUED", "message": "Reencolado tras reinicio"},
                )
                requeued += 1
            else:
                _fail_orphan(s, job.job_id, kind in IDEMPOTENT_KINDS)
                failed += 1
        s.commit()
        to_dispatch = [j.job_id for j in repo.with_status(JobStatus.queued)]
    for job_id in to_dispatch:
        dispatcher.submit(job_id)
    log.info(
        "jobs_recovered",
        extra={"requeued": requeued, "failed": failed, "redispatched": len(to_dispatch)},
    )
    return RecoveryReport(requeued, failed, len(to_dispatch))


def _fail_orphan(s: Session, job_id: UUID, idempotent: bool) -> None:
    reason = (
        "Intentos agotados tras reinicio" if idempotent else "Trabajo no idempotente interrumpido"
    )
    s.execute(
        update(Job)
        .where(Job.job_id == job_id, Job.status == JobStatus.running)
        .values(
            status=JobStatus.failed,
            finished_at=func.now(),
            error={"code": "ORPHANED", "type": "OrphanedJob", "message": reason},
        )
    )
