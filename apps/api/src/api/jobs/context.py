"""Contexto que recibe cada handler dentro del worker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.uow import UnitOfWork
from api.models.enums import JobStatus
from api.repositories.jobs import JobRepository
from api.storage.object_store import ObjectStore


class JobCancelled(Exception):
    """El trabajo fue cancelado; el handler debe abandonar sin escribir más."""


class JobTimedOut(Exception):
    """Se superó el timeout blando configurado."""


class RetryableJobError(Exception):
    """Fallo transitorio: el worker puede reintentar mientras queden intentos."""


@dataclass
class JobContext:
    job_id: UUID
    kind: str
    created_by: UUID | None
    attempt: int
    uow: UnitOfWork  # con app.user_id = creador del trabajo (RLS aplica)
    engine: Engine  # para escrituras autónomas de progreso (transacción propia)
    store: ObjectStore
    timeout_seconds: int = 0
    ports: object | None = None
    started: float = field(default_factory=time.monotonic)

    def _own_session(self) -> Session:
        return Session(self.engine)

    def check_cancelled(self) -> None:
        if self.timeout_seconds and time.monotonic() - self.started > self.timeout_seconds:
            raise JobTimedOut
        with self._own_session() as s:
            status = JobRepository(s).status_of(self.job_id)
        if status == JobStatus.cancelled:
            raise JobCancelled

    def progress(self, value: float) -> None:
        """Persiste el progreso en una transacción independiente de la del handler."""
        with self._own_session() as s:
            JobRepository(s).set_progress(self.job_id, value)
            s.commit()

    def checkpoint(self, result: dict[str, object]) -> None:
        """Guarda un resultado parcial (re-ejecución segura tras un reinicio)."""
        with self._own_session() as s:
            JobRepository(s).checkpoint_result(self.job_id, dict(result))
            s.commit()
