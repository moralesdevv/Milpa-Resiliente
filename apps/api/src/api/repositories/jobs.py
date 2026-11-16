"""Persistencia de ``engine.job``. Todas las transiciones son atómicas (UPDATE condicional)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models.engine import Job
from api.models.enums import JobKind, JobStatus


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, job_id: UUID) -> Job | None:
        return self.s.get(Job, job_id)

    def by_idempotency_key(self, key: str) -> Job | None:
        return self.s.scalar(select(Job).where(Job.idempotency_key == key))

    def create(
        self, kind: JobKind, payload: dict[str, Any], created_by: UUID | None, key: str | None
    ) -> tuple[Job, bool]:
        """Devuelve (job, creado). Con clave repetida devuelve el existente (creado=False)."""
        job = Job(
            kind=kind.value,
            status=JobStatus.queued,
            payload=payload,
            created_by=created_by,
            idempotency_key=key,
            attempts=0,
        )
        try:
            with self.s.begin_nested():  # savepoint: un conflicto no invalida la transacción
                self.s.add(job)
                self.s.flush()
        except IntegrityError:
            if key is None:
                raise
            existing = self.by_idempotency_key(key)
            if existing is None:
                raise
            return existing, False
        return job, True

    def claim(self, job_id: UUID) -> Job | None:
        """queued -> running de forma atómica. None si otro proceso lo tomó o fue cancelado."""
        row = self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status == JobStatus.queued)
            .values(
                status=JobStatus.running,
                attempts=Job.attempts + 1,
                started_at=_now(),
                progress=0.0,
                error=None,
            )
            .returning(Job.job_id)
        ).first()
        return self.get(job_id) if row else None

    def finish_ok(self, job_id: UUID, result: dict[str, Any]) -> bool:
        return self._finish(job_id, JobStatus.ok, result=result, progress=1.0)

    def finish_failed(self, job_id: UUID, error: dict[str, Any]) -> bool:
        return self._finish(job_id, JobStatus.failed, error=error)

    def _finish(self, job_id: UUID, status: JobStatus, **values: Any) -> bool:
        # Condición status='running': un trabajo cancelado no se "resucita" al terminar.
        res = self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status == JobStatus.running)
            .values(status=status, finished_at=_now(), **values)
            .returning(Job.job_id)
        ).first()
        return res is not None

    def set_progress(self, job_id: UUID, progress: float) -> None:
        self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status == JobStatus.running)
            .values(progress=max(0.0, min(1.0, progress)))
        )

    def checkpoint_result(self, job_id: UUID, result: dict[str, Any]) -> None:
        self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status == JobStatus.running)
            .values(result=result)
        )

    def requeue(self, job_id: UUID, error: dict[str, Any] | None = None) -> bool:
        res = self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status == JobStatus.running)
            .values(status=JobStatus.queued, started_at=None, error=error)
            .returning(Job.job_id)
        ).first()
        return res is not None

    def cancel(self, job_id: UUID) -> Job | None:
        """queued|running -> cancelled. Un trabajo terminado no cambia de estado."""
        self.s.execute(
            update(Job)
            .where(Job.job_id == job_id, Job.status.in_([JobStatus.queued, JobStatus.running]))
            .values(status=JobStatus.cancelled, finished_at=_now())
        )
        self.s.expire_all()
        return self.get(job_id)

    def status_of(self, job_id: UUID) -> JobStatus | None:
        return self.s.scalar(select(Job.status).where(Job.job_id == job_id))

    def with_status(self, *statuses: JobStatus) -> list[Job]:
        return list(
            self.s.scalars(select(Job).where(Job.status.in_(statuses)).order_by(Job.created_at))
        )


def _now() -> Any:
    return func.now()
