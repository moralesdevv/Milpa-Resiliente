"""Creación, consulta y cancelación de trabajos (spec R3 §13). Idempotencia por usuario."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from api.errors import ApiError, ErrorCode, NotFound, ValidationFailed
from api.models.engine import Job
from api.models.enums import JobKind, JobStatus, UserRole
from api.repositories.jobs import JobRepository
from api.schemas.jobs import JobOut
from api.services.context import ServiceContext

log = logging.getLogger("api.jobs")
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
PAYLOAD_VERSION = 1


class IdempotencyConflict(ApiError):
    status, code, title = 409, ErrorCode.IDEMPOTENCY_CONFLICT, "Conflicto de Idempotency-Key"


def job_location(job_id: UUID) -> str:
    return f"/v1/jobs/{job_id}"


def to_out(job: Job) -> JobOut:
    return JobOut(
        job_id=job.job_id,
        kind=JobKind(job.kind),
        status=job.status,
        progress=job.progress,
        result=job.result,
        error=job.error,
        attempts=job.attempts,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        location=job_location(job.job_id),
    )


class JobService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.repo = JobRepository(ctx.session)

    def submit(
        self, kind: JobKind, payload: dict[str, Any], idempotency_key: str | None
    ) -> tuple[Job, bool]:
        """Crea el registro ANTES de despachar (spec R3 §13.5). Devuelve (job, creado)."""
        key = self._scoped_key(idempotency_key)
        body = {"v": PAYLOAD_VERSION, **payload}
        job, created = self.repo.create(kind, body, self.ctx.user.user_id, key)
        if not created:
            if (
                job.created_by != self.ctx.user.user_id
                or job.kind != kind.value
                or job.payload != body
            ):
                self.ctx.uow.rollback()
                raise IdempotencyConflict(
                    "El Idempotency-Key ya se usó con una solicitud distinta",
                    hint="Use una clave nueva para una operación diferente.",
                )
            self.ctx.uow.rollback()
            return job, False
        self.ctx.uow.commit()
        try:
            self.ctx.dispatcher.submit(job.job_id)
        except Exception as exc:
            # Si el despacho falla, el job queda 'queued' y se redespacha al reiniciar
            # (recover_jobs); no se devuelve un 500 para una operación ya registrada.
            log.error(
                "job_dispatch_failed",
                extra={"job_id": str(job.job_id), "exc_type": type(exc).__name__},
            )
        # Con el despachador en línea (pruebas) el estado ya cambió: recargar.
        self.ctx.session.refresh(job)
        return job, True

    def existing(self, kind: JobKind, idempotency_key: str | None) -> Job | None:
        """Trabajo previo con la misma clave (del mismo usuario y tipo), sin crear nada."""
        key = self._scoped_key(idempotency_key)
        if key is None:
            return None
        job = self.repo.by_idempotency_key(key)
        if job is None:
            return None
        if job.created_by != self.ctx.user.user_id or job.kind != kind.value:
            raise IdempotencyConflict("El Idempotency-Key ya se usó con una solicitud distinta")
        return job

    def _scoped_key(self, key: str | None) -> str | None:
        if key is None:
            return None
        if not _KEY_RE.match(key):
            raise ValidationFailed(
                "Idempotency-Key inválido (1-128 caracteres: letras, dígitos, . _ : -)"
            )
        return f"{self.ctx.user.user_id}:{key}"  # por usuario: no filtra ni colisiona entre cuentas

    def get(self, job_id: UUID) -> Job:
        job = self.repo.get(job_id)
        user = self.ctx.user
        if job is None or (job.created_by != user.user_id and user.role != UserRole.admin):
            raise NotFound("Trabajo no encontrado")
        return job

    def cancel(self, job_id: UUID) -> Job:
        job = self.get(job_id)
        if job.status in (JobStatus.ok, JobStatus.failed, JobStatus.cancelled):
            return job  # ya terminado: la cancelación es idempotente y no cambia el estado
        cancelled = self.repo.cancel(job_id)
        self.ctx.uow.commit()
        if cancelled is None:  # no debería ocurrir: el trabajo existía hace un instante
            raise NotFound("Trabajo no encontrado")
        return cancelled
