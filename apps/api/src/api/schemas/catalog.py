from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.schemas.common import PROVISIONAL_R3

# Los catálogos son propiedad de R1 (ref.*). Estas formas reflejan columnas del DDL [Propuesto];
# su contrato público definitivo está pendiente (docs/integration/R1_DATA_CONTRACT.md).


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=PROVISIONAL_R3)

    crop_id: UUID
    code: str
    name_es: str
    name_en: str
    scientific_name: str | None
    family: str
    is_legume: bool | None
    fixes_n_conditions: str | None


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=PROVISIONAL_R3)

    strategy_id: UUID
    code: str
    name: str
    is_reference: bool
    changes_from_reference: list[str]
    latest_version: int | None = None  # versión publicada más reciente (None si no hay)


class StrategyComponentOut(BaseModel):
    variety_id: UUID
    crop_code: str | None = None
    crop_name_es: str | None = None
    crop_name_en: str | None = None
    role: str
    area_fraction: float
    plant_offset_days: int


class StrategyCycleOut(BaseModel):
    cycle_idx: int
    agri_year_offset: int
    season: str
    window_mode: str
    plant_window_start: str | None
    plant_window_end: str | None
    rel_lag_days: int | None
    fallow_after_days: int
    soil_carryover: bool
    components: list[StrategyComponentOut]


class StrategyVersionOut(BaseModel):
    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    strategy_version_id: UUID
    strategy_id: UUID
    version: int
    horizon_years: int
    anchor_cycle_idx: int
    cycles: list[StrategyCycleOut]


class ReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=PROVISIONAL_R3)

    citation_id: int
    bibkey: str
    full_text: str
    doi: str | None
    url: str | None
