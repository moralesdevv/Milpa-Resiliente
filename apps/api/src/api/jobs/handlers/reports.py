"""Handler ``report``: RunRef + ``EnginePort.build_report`` + adaptación a ReportInput + PDF.

El modelo de informe (R2) no existe: el handler falla con DEPENDENCY_NOT_INTEGRATED. El servicio
de generación (``ReportService``) sí es real y se prueba con una entrada provisional explícita.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from api.adapters.registry import load_ports
from api.errors import DependencyNotIntegrated
from api.jobs.context import JobContext
from api.jobs.registry import register
from api.models.enums import JobKind


@register(JobKind.report)
def report_job(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    from api.services.runs import run_ref_from_db

    run = run_ref_from_db(ctx.uow.session, UUID(payload["run_id"]))
    model = ports.engine.build_report(run, payload)  # R2: DependencyNotIntegrated hoy
    # PENDING_R2/R4: adaptar ReportModel -> ReportInput (api.reports.contract) y renderizar.
    raise DependencyNotIntegrated(
        "R2 (ReportModel) / R4 (plantilla final)",
        f"La conversión ReportModel->PDF (PENDING; claves={sorted(model)})",
    )
