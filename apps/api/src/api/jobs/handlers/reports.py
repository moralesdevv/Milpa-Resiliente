"""Handler ``report``: modelo de informe del motor (R2) → ``ReportInput`` → PDF (ReportLab) → registro.

El contenido sale del ``build_report`` de ``milpa_core``, de la cobertura/escenarios ya persistidos y de
los hashes de la corrida; R3 no calcula cifras. El PDF es Python puro (sin Pango ni Docker).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text

from api.adapters.registry import load_ports
from api.errors import NotFound
from api.jobs.context import JobContext
from api.jobs.registry import register
from api.models.enums import JobKind, UserRole
from api.reports.context import computed_scenarios, precip_coverage
from api.reports.contract import RunHashes
from api.reports.from_engine import report_input_from_model
from api.reports.service import ReportService
from api.services.context import CurrentUser, ServiceContext


@register(JobKind.report)
def report_job(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    from api.repositories.analysis import RunRepository
    from api.services.runs import run_ref_from_db

    session = ctx.uow.session
    run_id = UUID(payload["run_id"])
    run = run_ref_from_db(session, run_id)
    runs = RunRepository(session)
    row = runs.get(run_id)
    if row is None:
        raise NotFound("Corrida no encontrada")
    model = ports.engine.build_report(run, {"scenario_id": "BASE", "stability": {"seed": run.seed}})
    zone_name = session.execute(
        text("SELECT name FROM geo.zone WHERE zone_id = :z"), {"z": run.zone_id}
    ).scalar_one()
    hashes = RunHashes(
        code_version=run.code_version,
        region_config_hash=run.region_config_hash,
        catalog_hash=str(runs.catalog_hash(row.catalog_release_id) or "0" * 64),
        data_hash=run.data_hash,
        params_hash=run.params_hash,
        seed=run.seed,
    )
    coverage, data_window = precip_coverage(ctx.store, run.zone_id, str(zone_name))
    data = report_input_from_model(
        model,
        climate=ports.engine.climate_history(run, {}),
        coverage=coverage,
        data_window=data_window,
        scenarios=computed_scenarios(ports.engine, run, runs, run_id),
        zone_name=str(zone_name),
        run_id=run_id,
        hashes=hashes,
        locale=str(payload.get("locale", "es+en")),
        privacy_level=str(payload.get("privacy_level", "internal")),
    )
    user_id = ctx.created_by
    if user_id is None:
        raise NotFound("El trabajo no tiene usuario asociado")
    stand_in = cast(
        ServiceContext,
        SimpleNamespace(
            uow=ctx.uow,
            user=CurrentUser(user_id, UserRole.tecnico),
            store=ctx.store,
            session=session,
        ),
    )
    ranking = payload.get("ranking_id")
    report = ReportService(stand_in).generate(data, ranking_id=UUID(ranking) if ranking else None)
    return {"v": 1, "report_id": str(report.report_id), "has_pdf": bool(report.pdf_uri)}
