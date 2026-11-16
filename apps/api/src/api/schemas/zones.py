from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas.common import PROVISIONAL_R3
from api.schemas.runs import SourceOut

MAX_VERTICES = 20_000


class ZoneOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [
                {
                    "zone_id": "9f1a2b3c-4d5e-4f60-8a7b-1c2d3e4f5a6b",
                    "region_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
                    "name": "Zona de ejemplo (mock)",
                    "elevation_m": None,
                    "slope_pct": None,
                    "ready_at": None,
                }
            ],
        }
    )

    zone_id: UUID
    region_id: UUID
    name: str
    elevation_m: float | None = None
    slope_pct: float | None = None
    ready_at: datetime | None = None


class SoilEstimateAvailability(BaseModel):
    """Disponibilidad (no valores) de estimaciones espaciales de suelo por propiedad/profundidad."""

    property_code: str
    depth_label: str
    available: bool
    reason: str | None = None


class SourceComparison(BaseModel):
    """Comparación entre dos productos (R1: ``precip_validation.json``). NO es validación en la zona."""

    pair: str
    n_days_common: int | None = None
    bias_mm_day: float | None = Field(default=None, description="IMERG menos POWER, mm/día")
    correlation_daily: float | None = None
    correlation_dekad: float | None = None
    ratio_total: float | None = Field(default=None, description="Total IMERG / total POWER")
    annual_ratio: dict[str, float] = Field(default_factory=dict, description="IMERG/POWER por año")
    note: str | None = None


class ZoneCellOut(BaseModel):
    """Celda climática con su peso en la zona (``geo.zone_cell``). Nunca es una parcela."""

    cell_id: int
    source: str
    weight: float
    south: float
    west: float
    north: float
    east: float


class AgriContextOut(BaseModel):
    """Cultivos, temporadas y decisiones pendientes del region pack (sin definir nada nuevo)."""

    status: str
    region: str
    seasons: list[dict[str, Any]] = Field(default_factory=list)
    crops: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    source: str


class ZoneDetail(ZoneOut):
    geometry: dict[str, Any] = Field(description="GeoJSON (zona de análisis, dato público)")
    cells: list[ZoneCellOut] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)
    soil_estimates: list[SoilEstimateAvailability] = Field(default_factory=list)
    agri_context: AgriContextOut | None = None


def _count_vertices(coords: Any) -> int:
    if isinstance(coords, list) and coords and isinstance(coords[0], int | float):
        return 1
    return sum(_count_vertices(c) for c in coords) if isinstance(coords, list) else 0


def _is_position(p: Any) -> bool:
    return (
        isinstance(p, list)
        and len(p) == 2
        and all(isinstance(x, int | float) and not isinstance(x, bool) for x in p)
        and -180 <= p[0] <= 180
        and -90 <= p[1] <= 90
    )


def _is_ring(r: Any) -> bool:
    return isinstance(r, list) and len(r) >= 4 and all(_is_position(p) for p in r) and r[0] == r[-1]


def _is_polygon(c: Any) -> bool:
    return isinstance(c, list) and len(c) >= 1 and all(_is_ring(r) for r in c)


class ZoneCreate(BaseModel):
    """Crear zona e iniciar ingesta/curación externa (R1). Payload no definido en la spec."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    region_id: UUID
    name: str = Field(min_length=1, max_length=120)
    geometry: dict[str, Any]

    @field_validator("geometry")
    @classmethod
    def _geojson(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("geometry debe ser un GeoJSON Polygon o MultiPolygon")
        if set(v) - {"type", "coordinates"}:
            raise ValueError("geometry solo admite 'type' y 'coordinates'")
        coords = v.get("coordinates")
        if _count_vertices(coords) > MAX_VERTICES:
            raise ValueError(f"geometry excede {MAX_VERTICES} vértices")
        if v["type"] == "Polygon":
            ok = _is_polygon(coords)
        else:
            ok = (
                isinstance(coords, list)
                and len(coords) >= 1
                and all(_is_polygon(c) for c in coords)
            )
        if not ok:
            raise ValueError(
                "coordinates no es válido: anillos cerrados de >= 4 posiciones [lon, lat] en grados"
            )
        return v


class CoverageRow(BaseModel):
    """Fila de coverage.parquet (columnas del README §13.7; contrato pendiente de confirmar por R1)."""

    cell_id: int | None = None  # R1 entrega series por zona (sin celda)
    variable: str
    year: int
    n_expected: int | None = None
    n_valid: int | None = None
    pct_missing: float | None = None


class DatasetInfo(BaseModel):
    relative_path: str
    sha256: str
    n_rows: int
    contract_status: str


class DataQualityOut(BaseModel):
    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    zone_id: UUID
    dataset: DatasetInfo
    coverage: list[CoverageRow]
    next_cursor: str | None = None
    # Lo siguiente lo CALCULA R1 (`milpa-etl validate/merge`) y R3 solo lo transporta tal cual.
    state: Literal["ok", "insufficient_data"] = "ok"
    message: str | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    comparisons: list[SourceComparison] = Field(default_factory=list)
    ea_sensitivity_mm_day: float | None = Field(
        default=None,
        description="Diferencia media absoluta de ET0 entre las rutas T2MDEW y RH2M (R1)",
    )
    limitations: list[str] = Field(default_factory=list)
