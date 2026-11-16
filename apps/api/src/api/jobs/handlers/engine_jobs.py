"""Handlers que dependen de R1/R2. ESTADO: ``adapter_ready`` — sin integración verificada.

Cada handler comprueba el puerto; si la dependencia no está integrada, el trabajo falla con un
error tipado ``DEPENDENCY_NOT_INTEGRATED`` (nunca produce resultados). La persistencia del
resultado real (mapeo ``ScenarioRunResult`` -> ``engine.*``) está marcada PENDING_R2 porque el tipo
de retorno de R2 aún no existe.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from api.adapters.registry import load_ports
from api.errors import DependencyNotIntegrated
from api.jobs.context import JobContext
from api.jobs.registry import register
from api.models.enums import JobKind


@register(JobKind.zone_ingest)
def zone_ingest(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    result = ports.ingest.ingest_zone(UUID(payload["zone_id"]))  # R1: DependencyNotIntegrated
    return {"v": 1, "ingest": dict(result)}


@register(JobKind.analysis_run)
def analysis_run(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    outcome = ports.engine.run_base_analysis(payload)  # R2: DependencyNotIntegrated hoy
    # PENDING_R2: persistir engine.analysis_run/scenario_run/... a partir de ScenarioRunResult.
    raise DependencyNotIntegrated(
        ports.engine.component,
        f"La persistencia del resultado de la corrida (PENDING_R2: tipo de retorno no publicado; "
        f"claves recibidas={sorted(outcome)})",
    )


@register(JobKind.scenario_run)
def scenario_run(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    from api.services.runs import run_ref_from_db

    run = run_ref_from_db(ctx.uow.session, UUID(payload["run_id"]))
    outcome = ports.engine.run_scenarios(run, payload)  # R2: DependencyNotIntegrated hoy
    raise DependencyNotIntegrated(
        ports.engine.component,
        f"La persistencia de resultados de escenarios (PENDING_R2; claves={sorted(outcome)})",
    )
