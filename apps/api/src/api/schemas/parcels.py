from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.contracts.provisional_enums import PropertyStatus
from api.schemas.common import PROVISIONAL_R3

_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,63}$"


class GeoPoint(BaseModel):
    """Punto elegido en el mapa. Se generaliza en el servidor y NO se persiste ni se registra."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90, repr=False)
    lon: float = Field(ge=-180, le=180, repr=False)


class ParcelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    zone_id: UUID
    farmer_id: UUID | None = Field(
        default=None, description="Obligatorio para técnicos; el agricultor usa su propio perfil."
    )
    code: str | None = Field(default=None, pattern=_CODE_PATTERN, repr=False)
    area_ha: Decimal | None = Field(default=None, gt=0, le=100_000, decimal_places=2)
    location: GeoPoint = Field(repr=False)


class DisplayLocation(BaseModel):
    """Centro de celda de rejilla (>= 1 km), redondeado a 3 decimales. Nunca el punto original."""

    lat: float
    lon: float


class ParcelOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [
                {
                    "parcel_id": "7a1c0d4e-2b3f-4a5d-8e6f-9a0b1c2d3e4f",
                    "zone_id": "9f1a2b3c-4d5e-4f60-8a7b-1c2d3e4f5a6b",
                    "farmer_id": "1d2e3f4a-5b6c-4d7e-8f9a-0b1c2d3e4f5a",
                    "code": None,
                    "area_ha": "1.50",
                    "display_location": {"lat": 14.5, "lon": -89.5},
                    "display_grid_m": 1000,
                    "created_at": "2026-11-14T12:00:00Z",
                }
            ],
        }
    )

    parcel_id: UUID
    zone_id: UUID
    farmer_id: UUID | None
    code: str | None
    area_ha: Decimal | None
    display_location: DisplayLocation | None
    display_grid_m: int | None
    created_at: datetime


class SoilValue(BaseModel):
    """Valor almacenado + enlace de procedencia. NO es el ``Indicator`` de R2 (pendiente)."""

    value: float
    unit: str
    ip_id: UUID = Field(description="Use GET /v1/provenance/{ip_id} para el detalle de procedencia")


class SoilPropertyStatusOut(BaseModel):
    """Forma de SoilPropertyStatusDTO (README §15). ``value`` provisional hasta el Indicator de R2."""

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    property_code: str
    status: PropertyStatus
    value: SoilValue | None = None
    method: str | None = None
    depth_cm: tuple[int, int] | None = None
    sampled_at: date | None = None
    representativeness: str | None = None
    age_years: float | None = None
    max_age_years: int | None = None


class SoilDeclarationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    value: float
    unit: str | None = Field(default=None, max_length=32)
    basis: str = Field(min_length=1, max_length=500)


class SoilDeclarationOut(BaseModel):
    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    parcel_id: UUID
    property_code: str
    value: float
    unit: str
    basis: str
    declared_at: datetime
    ip_id: UUID


class CsvRowError(BaseModel):
    row: int | None = Field(
        description="Número de fila de datos (1 = primera fila tras el encabezado)"
    )
    column: str | None = None
    code: str
    msg: str


class SoilCsvResult(BaseModel):
    """Resultado de validar (y, si procede, guardar) un CSV de suelo.

    El formato del CSV de entrada lo fija la especificación; esta *respuesta* no está definida
    en ella y es una forma propuesta por R3.
    """

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    contract: str = Field(description="Versión del esquema CSV aplicado (``SOIL_CSV_V1``)")
    rows_total: int
    rows_accepted: int
    accepted_by_property: dict[str, int]
    persisted: bool
    dry_run: bool


class PriorityProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    w_water: Decimal = Field(ge=0, le=1, decimal_places=3)
    w_soil: Decimal = Field(ge=0, le=1, decimal_places=3)
    w_food: Decimal = Field(ge=0, le=1, decimal_places=3)
    w_income: Decimal = Field(ge=0, le=1, decimal_places=3)
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Restricciones tal como las declaró el agricultor (semilla, mano de obra, mercado, riego).",
    )

    @model_validator(mode="after")
    def _sum_to_one(self) -> PriorityProfileIn:
        total = self.w_water + self.w_soil + self.w_food + self.w_income
        if abs(total - Decimal(1)) >= Decimal("0.001"):  # mismo criterio que el CHECK de la BD
            raise ValueError("Los pesos deben sumar 1 (tolerancia 0.001)")
        return self

    @field_validator("constraints")
    @classmethod
    def _bounded(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v, default=str)) > 4096:
            raise ValueError("constraints excede 4 KiB")
        if _depth(v) > 3:
            raise ValueError("constraints admite como máximo 3 niveles de anidación")
        if any(not isinstance(k, str) or len(k) > 64 for k in v):
            raise ValueError("Las claves de constraints deben ser texto de hasta 64 caracteres")
        return v


def _depth(obj: Any, level: int = 0) -> int:
    if isinstance(obj, dict):
        return max([_depth(v, level + 1) for v in obj.values()] or [level + 1])
    if isinstance(obj, list):
        return max([_depth(v, level + 1) for v in obj] or [level + 1])
    return level


class PriorityProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=PROVISIONAL_R3)

    parcel_id: UUID
    w_water: Decimal
    w_soil: Decimal
    w_food: Decimal
    w_income: Decimal
    constraints: dict[str, Any]
    updated_at: datetime
