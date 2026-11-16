from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from api.dependencies.core import CtxDep, IdempotencyKey
from api.routers._common import AUTHED, ZoneId, accepted, error_responses
from api.schemas.common import Page
from api.schemas.jobs import JobOut
from api.schemas.runs import RunCreate
from api.schemas.zones import DataQualityOut, ZoneCreate, ZoneDetail, ZoneOut
from api.services.runs import RunService
from api.services.zones import ZoneService

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get(
    "",
    response_model=Page[ZoneOut],
    summary="Listar zonas",
    description="Roles: todos los autenticados. Paginación por cursor.",
    responses=AUTHED,
)
def list_zones(
    ctx: CtxDep, cursor: str | None = None, limit: Annotated[int | None, Query(ge=1)] = None
) -> Page[ZoneOut]:
    return ZoneService(ctx).list(cursor, limit)


@router.get(
    "/{id}",
    response_model=ZoneDetail,
    summary="Consultar zona",
    description="Contexto de zona (dato público de análisis, no de parcelas).",
    responses={**AUTHED, **error_responses(404)},
)
def get_zone(zone_id: ZoneId, ctx: CtxDep) -> ZoneDetail:
    return ZoneService(ctx).get(zone_id)


@router.post(
    "",
    response_model=JobOut,
    status_code=202,
    summary="Crear zona e iniciar ingesta",
    description="Roles: tecnico, admin. Trabajo asíncrono (202 + Location). La ingesta y "
    "curación son de R1: sin R1 integrado el trabajo termina en `failed` con "
    "`DEPENDENCY_NOT_INTEGRATED`. Admite `Idempotency-Key`.",
    responses={**AUTHED, **error_responses(409, 422)},
)
def create_zone(
    body: ZoneCreate, ctx: CtxDep, response: Response, idempotency_key: IdempotencyKey = None
) -> JobOut:
    job, _ = ZoneService(ctx).create(body, idempotency_key)
    return accepted(job, response)


@router.get(
    "/{id}/data-quality",
    response_model=DataQualityOut,
    summary="Calidad/cobertura de datos de la zona",
    description="Lee `curated/<zona>/coverage.parquet` (contrato propuesto, pendiente de "
    "confirmar por R1). 503 `DATASET_UNAVAILABLE` si el archivo no existe, "
    "`DATASET_INCOMPATIBLE` si no cumple el contrato.",
    responses={**AUTHED, **error_responses(404, 503)},
)
def data_quality(
    zone_id: ZoneId,
    ctx: CtxDep,
    variable: str | None = None,
    year: Annotated[int | None, Query(ge=1900, le=2200)] = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> DataQualityOut:
    return ZoneService(ctx).data_quality(zone_id, variable, year, cursor, limit)


@router.post(
    "/{id}/runs",
    response_model=JobOut,
    status_code=202,
    tags=["runs"],
    summary="Crear corrida base",
    description="Roles: tecnico, admin. Trabajo asíncrono. Requiere `milpa_core` (R2); sin "
    "él el trabajo falla con `DEPENDENCY_NOT_INTEGRATED`.",
    responses={**AUTHED, **error_responses(404, 409, 422)},
)
def create_run(
    zone_id: ZoneId,
    body: RunCreate,
    ctx: CtxDep,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> JobOut:
    job, _ = RunService(ctx).create_base_run(zone_id, body, idempotency_key)
    return accepted(job, response)
