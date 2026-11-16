from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from api.dependencies.core import CtxDep
from api.routers._common import AUTHED, StrategyId, StrategyVersionNo, error_responses
from api.schemas.catalog import CropOut, ReferenceOut, StrategyOut, StrategyVersionOut
from api.schemas.common import Page
from api.services.catalog_reports import CatalogService

LimitQ = Annotated[int | None, Query(ge=1)]
router = APIRouter(prefix="/catalog", tags=["catalog"])
NOTE = "Catálogo de R1 (ref.*). Roles: todos los autenticados. Vacío hasta que R1 cargue datos."


@router.get(
    "/crops",
    response_model=Page[CropOut],
    summary="Catálogo de cultivos",
    description=NOTE,
    responses=AUTHED,
)
def crops(ctx: CtxDep, cursor: str | None = None, limit: LimitQ = None) -> Page[CropOut]:
    return CatalogService(ctx).crops(cursor, limit)


@router.get(
    "/strategies",
    response_model=Page[StrategyOut],
    summary="Catálogo de estrategias",
    description=NOTE,
    responses=AUTHED,
)
def strategies(ctx: CtxDep, cursor: str | None = None, limit: LimitQ = None) -> Page[StrategyOut]:
    return CatalogService(ctx).strategies(cursor, limit)


@router.get(
    "/strategies/{id}/versions/{v}",
    response_model=StrategyVersionOut,
    summary="Versión de estrategia",
    description=NOTE,
    responses={**AUTHED, **error_responses(404)},
)
def strategy_version(
    strategy_id: StrategyId, version: StrategyVersionNo, ctx: CtxDep
) -> StrategyVersionOut:
    return CatalogService(ctx).strategy_version(strategy_id, version)


@router.get(
    "/references",
    response_model=Page[ReferenceOut],
    summary="Referencias bibliográficas",
    description=NOTE,
    responses=AUTHED,
)
def references(ctx: CtxDep, cursor: str | None = None, limit: LimitQ = None) -> Page[ReferenceOut]:
    return CatalogService(ctx).references(cursor, limit)
