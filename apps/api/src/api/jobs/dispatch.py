"""Despacho de trabajos: ``ProcessPoolExecutor`` (concurrent.futures), spawn, sin cola externa.

Separación API/worker (spec R3 §4.3, §13.5): al worker solo viajan datos serializables
(``WorkerConfig`` + ``job_id``); cada proceso crea su propio Engine/Session. No se envían secretos
JWT al worker.
"""

from __future__ import annotations

import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from api.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerConfig:
    """Subconjunto serializable de la configuración que necesita un worker."""

    database_url: str
    data_dir: str
    max_attempts: int
    timeout_seconds: int
    exact_geometry_enabled: bool = False

    @classmethod
    def from_settings(cls, s: Settings) -> WorkerConfig:
        return cls(
            database_url=s.database_url,
            data_dir=str(Path(s.data_dir).resolve()),
            max_attempts=s.job_max_attempts,
            timeout_seconds=s.job_timeout_seconds,
        )


class JobDispatcher(Protocol):
    def submit(self, job_id: UUID) -> None: ...
    def shutdown(self) -> None: ...


def _worker_entry(job_id: str, cfg: dict[str, Any]) -> None:
    from api.jobs.worker import run_job

    run_job(UUID(job_id), WorkerConfig(**cfg))


class ProcessPoolDispatcher:
    def __init__(self, config: WorkerConfig, max_workers: int) -> None:
        self.config = config
        self.max_workers = max_workers
        self._pool: ProcessPoolExecutor | None = None
        self._futures: dict[UUID, Future[None]] = {}

    def _executor(self) -> ProcessPoolExecutor:
        if self._pool is None:
            # spawn: proceso limpio, nunca hereda conexiones/engines del proceso API.
            self._pool = ProcessPoolExecutor(
                max_workers=self.max_workers, mp_context=multiprocessing.get_context("spawn")
            )
        return self._pool

    def submit(self, job_id: UUID) -> None:
        try:
            fut = self._executor().submit(_worker_entry, str(job_id), asdict(self.config))
        except BrokenProcessPool:
            # Un worker murió (p. ej. por falta de memoria): el pool queda inutilizable; se recrea una vez.
            self._pool = None
            fut = self._executor().submit(_worker_entry, str(job_id), asdict(self.config))
        self._futures[job_id] = fut
        fut.add_done_callback(lambda f: self._done(job_id, f))

    def _done(self, job_id: UUID, fut: Future[None]) -> None:
        self._futures.pop(job_id, None)
        if fut.cancelled():
            return
        exc = fut.exception()
        if exc is not None:
            # El worker ya persiste su propio fallo; aquí solo cae una falla del pool (p. ej. OOM).
            log.error(
                "worker_crashed", extra={"job_id": str(job_id), "exc_type": type(exc).__name__}
            )

    def try_cancel(self, job_id: UUID) -> bool:
        fut = self._futures.get(job_id)
        return bool(fut and fut.cancel())

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None


class InlineDispatcher:
    """Ejecuta en el mismo proceso (hilo del llamador). SOLO para pruebas y CLI.

    Mantiene la separación de sesiones: ``run_job`` abre su propio Engine/Session.
    """

    def __init__(
        self, config: WorkerConfig, runner: Callable[[UUID, WorkerConfig], None] | None = None
    ) -> None:
        self.config = config
        self.runner = runner
        self.submitted: list[UUID] = []

    def submit(self, job_id: UUID) -> None:
        from api.jobs.worker import run_job

        self.submitted.append(job_id)
        (self.runner or run_job)(job_id, self.config)

    def shutdown(self) -> None:
        return None


class NullDispatcher:
    """No ejecuta nada: deja los trabajos en 'queued' (pruebas de estado/recuperación)."""

    def __init__(self) -> None:
        self.submitted: list[UUID] = []

    def submit(self, job_id: UUID) -> None:
        self.submitted.append(job_id)

    def shutdown(self) -> None:
        return None
