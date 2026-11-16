"""Registro de handlers y política por tipo de trabajo (spec R3 §13).

Idempotencia: solo los trabajos idempotentes se reencolan tras un reinicio; los demás pasan a
``failed`` con motivo. ``zone_ingest`` se declara NO idempotente hasta que R1 confirme su contrato
(manifiesto por partición); es decisión conservadora y está documentada en docs/JOBS.md.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.jobs.context import JobContext
from api.models.enums import JobKind

Handler = Callable[[JobContext, dict[str, Any]], dict[str, Any]]

IDEMPOTENT_KINDS: frozenset[JobKind] = frozenset(
    {
        JobKind.analysis_run,
        JobKind.scenario_run,
        JobKind.report,
        JobKind.parcel_delete,
        JobKind.consent_purge,
    }
)

_HANDLERS: dict[str, Handler] = {}


def register(kind: JobKind) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[kind.value] = fn
        return fn

    return deco


def get_handler(kind: str) -> Handler | None:
    import api.jobs.handlers  # noqa: F401  (importa y registra los handlers)

    return _HANDLERS.get(kind)


def override_handler(kind: JobKind, fn: Handler | None) -> Handler | None:
    """Solo pruebas/benchmarks. Devuelve el handler previo para poder restaurarlo."""
    get_handler(kind.value)  # garantiza que los handlers reales ya estén registrados
    previous = _HANDLERS.get(kind.value)
    if fn is None:
        _HANDLERS.pop(kind.value, None)
    else:
        _HANDLERS[kind.value] = fn
    return previous
