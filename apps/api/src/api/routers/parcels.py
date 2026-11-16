from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.dependencies.core import CtxDep, IdempotencyKey
from api.routers._common import (
    AUTHED,
    ParcelId,
    SoilPropertyCode,
    accepted,
    error_responses,
    read_limited_body,
)
from api.schemas.jobs import JobOut
from api.schemas.parcels import (
    ParcelCreate,
    ParcelOut,
    PriorityProfileIn,
    PriorityProfileOut,
    SoilCsvResult,
    SoilDeclarationIn,
    SoilDeclarationOut,
    SoilPropertyStatusOut,
)
from api.services.parcels import ParcelService, ProfileService, SoilService

router = APIRouter(prefix="/parcels", tags=["parcels"])
OWNER_NOTE = "Roles: dueño (agricultor) o técnico asignado con consentimiento vigente."


@router.post(
    "",
    response_model=ParcelOut,
    status_code=201,
    summary="Crear parcela",
    description="Roles: agricultor, tecnico. La ubicación se generaliza en el servidor a una "
    "rejilla de al menos 1 km; el punto original NO se persiste ni se registra. "
    "Requiere consentimiento `analysis` vigente.",
    responses={**AUTHED, **error_responses(404, 422)},
)
def create_parcel(body: ParcelCreate, ctx: CtxDep) -> ParcelOut:
    return ParcelService(ctx).create(body)


@router.get(
    "/{id}",
    response_model=ParcelOut,
    summary="Consultar parcela",
    description=OWNER_NOTE,
    responses={**AUTHED, **error_responses(404)},
)
def get_parcel(parcel_id: ParcelId, ctx: CtxDep) -> ParcelOut:
    return ParcelService(ctx).get(parcel_id)


@router.delete(
    "/{id}",
    response_model=JobOut,
    status_code=202,
    summary="Borrado definitivo de la parcela (trabajo)",
    description="Solo el dueño (la vía admin está bloqueada hasta aprobar la política de "
    "acceso excepcional, ADR-015). Elimina parcela, suelo, historial, perfiles, corridas, "
    "resultados Parquet, informes y PDFs.",
    responses={**AUTHED, **error_responses(404)},
)
def delete_parcel(
    parcel_id: ParcelId, ctx: CtxDep, response: Response, idempotency_key: IdempotencyKey = None
) -> JobOut:
    job, _ = ParcelService(ctx).request_delete(parcel_id, idempotency_key)
    return accepted(job, response)


@router.get(
    "/{id}/soil",
    response_model=list[SoilPropertyStatusOut],
    summary="Estado del suelo por propiedad",
    description=OWNER_NOTE,
    responses={**AUTHED, **error_responses(404)},
)
def soil_status(parcel_id: ParcelId, ctx: CtxDep) -> list[SoilPropertyStatusOut]:
    return SoilService(ctx).status(parcel_id)


@router.post(
    "/{id}/soil-samples",
    response_model=SoilCsvResult,
    summary="Subir y validar CSV de suelo",
    description=OWNER_NOTE + " Cuerpo: `text/csv` (UTF-8). Formato CSV definido por la "
    "especificación integral (apartado 9; contrato `SOIL_CSV_V1`); `parcel_code` debe coincidir "
    "con el código de la parcela. Con `dry_run=true` solo valida. Guardar "
    "requiere reglas de evidencia de R2 (503 `DEPENDENCY_NOT_INTEGRATED` si faltan). "
    "Todo o nada: cualquier error por fila/propiedad rechaza el archivo (422).",
    responses={**AUTHED, **error_responses(404, 413, 415, 422, 503)},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload_soil_csv(
    parcel_id: ParcelId, request: Request, ctx: CtxDep, dry_run: bool = False
) -> SoilCsvResult:
    raw = await read_limited_body(
        request, ctx.settings.max_upload_bytes, ("text/csv", "application/csv")
    )
    return SoilService(ctx).upload_csv(parcel_id, raw, dry_run=dry_run)


@router.put(
    "/{id}/soil-declarations/{property}",
    response_model=SoilDeclarationOut,
    summary="Declarar una propiedad de suelo",
    description=OWNER_NOTE + " Guardar requiere reglas de evidencia de R2 (503 si faltan).",
    responses={**AUTHED, **error_responses(404, 422, 503)},
)
def declare_soil(
    parcel_id: ParcelId, property_code: SoilPropertyCode, body: SoilDeclarationIn, ctx: CtxDep
) -> SoilDeclarationOut:
    return SoilService(ctx).declare(parcel_id, property_code, body)


@router.put(
    "/{id}/priority-profile",
    response_model=PriorityProfileOut,
    summary="Guardar perfil de prioridades y restricciones",
    description=OWNER_NOTE,
    responses={**AUTHED, **error_responses(404, 422)},
)
def save_profile(parcel_id: ParcelId, body: PriorityProfileIn, ctx: CtxDep) -> PriorityProfileOut:
    return ProfileService(ctx).save(parcel_id, body)
