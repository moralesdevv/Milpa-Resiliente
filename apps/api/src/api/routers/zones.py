from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from api.dependencies.core import CtxDep, IdempotencyKey
from api.routers._common import AUTHED, ZoneId, accepted, error_responses
from api.schemas.agronomy import (
    PlantingOptionsResponse,
    RainySeasonOnsetResponse,
    StationValidationResponse,
)
from api.schemas.common import Page
from api.schemas.jobs import JobOut
from api.schemas.parcels import PlantingValidationRequest, PlantingValidationResponse
from api.schemas.runs import RunCreate
from api.schemas.zones import DataQualityOut, ZoneCreate, ZoneDetail, ZoneOut
from api.services.agronomy import AgronomyService
from api.services.planting import PlantingValidationService
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


@router.get(
    "/{id}/planting-validation",
    response_model=PlantingValidationResponse,
    summary="Validar cultivo, variedad, ciclo y fecha de siembra en Jocotán",
    description=(
        "Evaluación de solo lectura con reglas provisionales (reglas_agronomicas_jocotan.json) y, si no se indican "
        "datos propios, clima histórico zonal. Disponible en sesión demo; no es pronóstico ni medición parcelaria. "
        "Una fecha fuera de la ventana es una advertencia de compatibilidad, no una prohibición."
    ),
    responses={**AUTHED, **error_responses(404, 422, 503)},
)
def validate_zone_planting(
    zone_id: ZoneId,
    ctx: CtxDep,
    fecha_siembra: date,
    variedad: Annotated[str, Query(min_length=1, max_length=80)],
    cultivo: Annotated[str, Query(min_length=1, max_length=40)] = "maiz",
    ciclo: Annotated[str | None, Query(max_length=20)] = None,
    dias_secos_recientes: Annotated[int | None, Query(ge=0, le=366)] = None,
    lluvia_15_dias_mm: Annotated[float | None, Query(ge=0, le=2000)] = None,
    idioma: Annotated[Literal["es", "en"], Query()] = "es",
) -> PlantingValidationResponse:
    request = PlantingValidationRequest(
        fecha_siembra=fecha_siembra,
        variedad=variedad,
        cultivo=cultivo,
        ciclo=ciclo,
        dias_secos_recientes=dias_secos_recientes,
        lluvia_15_dias_mm=lluvia_15_dias_mm,
        idioma=idioma,
    )
    return PlantingValidationService(ctx).validate_zone(zone_id, request)


@router.get(
    "/{id}/planting-options",
    response_model=PlantingOptionsResponse,
    summary="Cultivos, variedades y ciclos configurados para la validación de siembra",
    description="Lee reglas_agronomicas_jocotan.json; los valores son provisionales hasta la validación oficial MAGA/ICTA.",
    responses={**AUTHED, **error_responses(404, 422, 503)},
)
def planting_options(zone_id: ZoneId, ctx: CtxDep) -> PlantingOptionsResponse:
    return AgronomyService(ctx).planting_options(zone_id)


@router.get(
    "/{id}/rainy-season-onset",
    response_model=RainySeasonOnsetResponse,
    summary="Estimación SANDBOX del inicio de la época lluviosa (pentadas)",
    description=(
        "Aplica un criterio de pentadas configurable (MAGA Informe 6/2025) a la precipitación diaria curada de la zona. "
        "No es un boletín ni el método oficial de INSIVUMEH; no usar como única base de decisiones. "
        "Con fecha_siembra compara en días la siembra con el inicio estimado."
    ),
    responses={**AUTHED, **error_responses(404, 422, 503)},
)
def rainy_season_onset(
    zone_id: ZoneId,
    ctx: CtxDep,
    anio: Annotated[int | None, Query(ge=1981, le=2100)] = None,
    fecha_siembra: date | None = None,
    idioma: Annotated[Literal["es", "en"], Query()] = "es",
) -> RainySeasonOnsetResponse:
    return AgronomyService(ctx).rainy_season_onset(zone_id, anio, fecha_siembra, idioma)


@router.get(
    "/{id}/station-validation",
    response_model=StationValidationResponse,
    summary="Estado de la validación de la lluvia satelital contra la estación Camotán",
    description=(
        "Por defecto «Nivel C - Pendiente»: no hay serie histórica de la estación. Solo un CSV real colocado por el "
        "operador en el servidor, con suficientes días coincidentes, puede pasar a «Nivel B - Validado localmente». "
        "El archivo de ejemplo ficticio nunca cambia el estado."
    ),
    responses={**AUTHED, **error_responses(404, 422, 503)},
)
def station_validation(
    zone_id: ZoneId, ctx: CtxDep, idioma: Annotated[Literal["es", "en"], Query()] = "es"
) -> StationValidationResponse:
    return AgronomyService(ctx).station_validation(zone_id, idioma)


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
