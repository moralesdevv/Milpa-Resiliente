from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from api.contracts.provisional_enums import AdaptationMode
from api.dependencies.core import CtxDep, IdempotencyKey
from api.routers._common import AUTHED, RunId, accepted, error_responses, not_modified
from api.schemas.jobs import JobOut
from api.schemas.runs import (
    ClimateHistoryPayload,
    DekadChartPayload,
    HeatmapPayload,
    ProvenanceOut,
    RankRequest,
    RankResponsePayload,
    RunOut,
    ScenariosCreate,
    ScenarioTag,
    SoilVoiPayload,
    SoilVoiRequest,
    StrategyRiskPayload,
)
from api.services.runs import ProvenanceService, RunService, etag_for

router = APIRouter(prefix="/runs", tags=["runs"])
NOT_INTEGRATED = (
    " Requiere el motor `milpa_core` (R2): hasta su integración responde 503 "
    "`DEPENDENCY_NOT_INTEGRATED`; nunca devuelve datos simulados. Un escenario no calculado "
    "responde 409 `SCENARIO_NOT_COMPUTED`."
)
# R2 identifica estrategias y variedades por código (p. ej. E1_REF_MAIZ), no por UUID.
CodeParam = Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_.-]{1,64}$")]

READ_ERRORS = {**AUTHED, **error_responses(404, 409, 503)}


@router.get(
    "/{id}",
    response_model=RunOut,
    summary="Estado, modo, razones y hashes de la corrida",
    description="Roles: usuarios con acceso a la corrida. Soporta ETag / If-None-Match.",
    responses={**AUTHED, **error_responses(404)},
)
def get_run(run_id: RunId, request: Request, ctx: CtxDep) -> Any:
    svc = RunService(ctx)
    run = svc.get(run_id)
    etag = etag_for(run, "run", {})
    if (resp := not_modified(request, etag)) is not None:
        return resp
    return _json(svc.to_out(run), etag)


@router.get(
    "/{id}/scenarios",
    response_model=list[ScenarioTag],
    summary="Escenarios y lecturas ya calculados",
    responses=READ_ERRORS,
)
def list_scenarios(run_id: RunId, request: Request, ctx: CtxDep) -> Any:
    svc = RunService(ctx)
    run = svc.get(run_id)
    etag = etag_for(run, "scenarios", {"n": len(svc.runs.scenarios(run_id))})
    if (resp := not_modified(request, etag)) is not None:
        return resp
    tags = svc.scenarios(run_id)
    return Response(
        content=json.dumps([t.model_dump(mode="json") for t in tags]),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, no-cache"},
    )


@router.post(
    "/{id}/scenarios",
    response_model=JobOut,
    status_code=202,
    summary="Ejecutar grilla/combinaciones nuevas (trabajo)",
    description="Roles: tecnico, admin." + NOT_INTEGRATED,
    responses=READ_ERRORS,
)
def create_scenarios(
    run_id: RunId,
    body: ScenariosCreate,
    ctx: CtxDep,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> JobOut:
    job, _ = RunService(ctx).create_scenarios(run_id, body, idempotency_key)
    return accepted(job, response)


@router.get(
    "/{id}/climate-history",
    response_model=ClimateHistoryPayload,
    summary="Historial climático (resumen de 25 años)",
    description=NOT_INTEGRATED,
    responses=READ_ERRORS,
)
def climate_history(run_id: RunId, ctx: CtxDep) -> Any:
    return RunService(ctx).present("climate_history", run_id, {})


@router.get(
    "/{id}/summary",
    response_model=StrategyRiskPayload,
    summary="Resumen de riesgo (StrategyRiskDTO[])",
    description=NOT_INTEGRATED,
    responses=READ_ERRORS,
)
def summary(
    run_id: RunId,
    ctx: CtxDep,
    scenario: str | None = None,
    adaptation: AdaptationMode = AdaptationMode.none,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> Any:
    return RunService(ctx).present(
        "summary",
        run_id,
        {"scenario": scenario, "adaptation": adaptation.value, "cursor": cursor, "limit": limit},
    )


@router.get(
    "/{id}/heatmap",
    response_model=HeatmapPayload,
    summary="Datos del heatmap (HeatmapDTO)",
    description=NOT_INTEGRATED,
    responses=READ_ERRORS,
)
def heatmap(
    run_id: RunId,
    ctx: CtxDep,
    view: str | None = None,
    strategy: CodeParam = None,
    cycle: Annotated[int | None, Query(ge=0, le=1000)] = None,
    variety: CodeParam = None,
    scenario: str | None = None,
    adaptation: AdaptationMode = AdaptationMode.none,
) -> Any:
    params = {
        "view": view,
        "strategy": strategy,
        "cycle": cycle,
        "variety": variety,
        "scenario": scenario,
        "adaptation": adaptation.value,
    }
    return RunService(ctx).present("heatmap", run_id, params)


@router.get(
    "/{id}/dekad-chart",
    response_model=DekadChartPayload,
    summary="Gráfico por decena (DekadChartDTO)",
    description=NOT_INTEGRATED,
    responses=READ_ERRORS,
)
def dekad_chart(
    run_id: RunId,
    ctx: CtxDep,
    strategy: CodeParam = None,
    cohort_year: Annotated[int | None, Query(ge=1900, le=2200)] = None,
    cycle: Annotated[int | None, Query(ge=0, le=1000)] = None,
    plant_date: date | None = None,
    scenario: str | None = None,
) -> Any:
    params = {
        "strategy": strategy,
        "cohort_year": cohort_year,
        "cycle": cycle,
        "plant_date": plant_date.isoformat() if plant_date else None,
        "scenario": scenario,
    }
    return RunService(ctx).present("dekad_chart", run_id, params)


@router.post(
    "/{id}/rank",
    response_model=RankResponsePayload,
    summary="Ranking y estabilidad (RankRequest -> RankResponse)",
    description="Operación síncrona sobre resultados ya calculados." + NOT_INTEGRATED,
    responses={**READ_ERRORS, **error_responses(422)},
)
def rank(run_id: RunId, body: RankRequest, ctx: CtxDep) -> Any:
    return RunService(ctx).rank(run_id, body)


@router.post(
    "/{id}/soil-voi",
    response_model=SoilVoiPayload,
    summary="Valor de la información del suelo (SoilVoiResponse)",
    description="Roles: dueño o técnico asignado." + NOT_INTEGRATED,
    responses={**READ_ERRORS, **error_responses(422)},
)
def soil_voi(run_id: RunId, ctx: CtxDep, body: SoilVoiRequest | None = None) -> Any:
    return RunService(ctx).soil_voi(run_id, body)


provenance_router = APIRouter(prefix="/provenance", tags=["provenance"])


@provenance_router.get(
    "/{ip_id}",
    response_model=ProvenanceOut,
    summary="Detalle de procedencia",
    description="Roles: usuarios con acceso al recurso al que pertenece el "
    "indicador. 404 si no existe o no es visible.",
    responses={**AUTHED, **error_responses(404)},
)
def get_provenance(ip_id: UUID, ctx: CtxDep) -> ProvenanceOut:
    return ProvenanceService(ctx).get(ip_id)


def _json(model: Any, etag: str) -> Response:
    return Response(
        content=model.model_dump_json(),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, no-cache"},
    )
