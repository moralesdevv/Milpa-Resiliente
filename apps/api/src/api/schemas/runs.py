from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.contracts.provisional_enums import AdaptationMode, HumidityAssumption, Label
from api.schemas.common import PROVISIONAL_R3, OpaqueJson, pending

SCENARIO_ID_PATTERN = (
    r"^(BASE|T[+-]\d+_P[+-]\d+_D[+-]\d+_H(na|rh|ea))$"  # README §13.6 (comentario)
)


class RunCreate(BaseModel):
    """Corrida base. El payload no está definido en la spec; ``params`` es opaco (lo define R2)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    period_start: date
    period_end: date
    parcel_id: UUID | None = None
    seed: int = Field(ge=0, lt=2**63, description="Semilla explícita (README §25)")
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _period(self) -> RunCreate:
        if self.period_end < self.period_start:
            raise ValueError("period_end no puede ser anterior a period_start")
        return self


class RunOut(BaseModel):
    """Estado, modo, razones y hashes de la corrida (README §16). Solo columnas del DDL."""

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    run_id: UUID
    zone_id: UUID
    parcel_id: UUID | None
    period_start: date
    period_end: date
    mode: str
    # Pareja modo→etiqueta fijada por el README (glosario); la decide el motor, aquí solo se refleja.
    label: Label | None = None
    mode_reasons: list[str]
    status: str
    params_hash: str
    region_config_hash: str
    catalog_release_id: UUID
    catalog_hash: str | None = None
    # Banderas del motor guardadas en `params` (R2); ausentes ⇒ desconocidas, nunca «falso» inventado
    sandbox: bool | None = None
    synthetic_fixture: bool | None = None
    data_hash: str
    code_version: str
    seed: int
    created_at: datetime | None


class ScenarioTag(BaseModel):
    """``ScenarioTag`` del README §15: identifica sin ambigüedad qué escenario se calculó.

    Se arma solo con ``engine.scenario_def`` + ``engine.scenario_run`` (no calcula nada). Los parámetros
    de la perturbación los define R2; aquí se transportan tal como están registrados.
    """

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    scenario_id: str
    label: Literal["escenario sintético"]
    delta_t_c: float
    precip_factor: float
    onset_delay_days: int
    humidity_assumption: HumidityAssumption
    adaptation_mode: AdaptationMode
    method_doc: str
    engine_version: str
    executed_at: datetime


class ScenariosCreate(BaseModel):
    """Ejecutar grilla/combinaciones nuevas. La grilla la define R2; aquí solo se transportan ids."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    scenario_ids: list[str] | None = Field(
        default=None, max_length=64, description="None = la grilla completa que defina R2"
    )
    adaptation_modes: list[AdaptationMode] = Field(
        default_factory=lambda: [AdaptationMode.none], min_length=1, max_length=2
    )


class Weights(BaseModel):
    """water, soil, food, income; suman 1 ± 1e-6 (README §15)."""

    model_config = ConfigDict(extra="forbid")

    water: float = Field(ge=0, le=1)
    soil: float = Field(ge=0, le=1)
    food: float = Field(ge=0, le=1)
    income: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sum(self) -> Weights:
        if abs(self.water + self.soil + self.food + self.income - 1.0) > 1e-6:
            raise ValueError("Los pesos deben sumar 1 (tolerancia 1e-6)")
        return self


class StabilityRequest(BaseModel):
    """n_samples, mode, concentration | radius, seed (README §15). Semántica: R2."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    n_samples: int | None = Field(
        default=None,
        ge=1,
        le=100_000,
        description="Tope de seguridad de R3 (provisional). Ausente = lo decide el motor (R2)",
    )
    mode: str = Field(min_length=1, max_length=32)
    concentration: float | None = Field(default=None, gt=0)
    radius: float | None = Field(default=None, gt=0)
    seed: int = Field(ge=0, lt=2**63)


class RankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    scenario_id: str = Field(pattern=SCENARIO_ID_PATTERN)
    adaptation_mode: AdaptationMode = AdaptationMode.none
    weights: Weights
    missing_policy: Literal["common_support", "exclude_incomplete"] = "common_support"
    stability: StabilityRequest


class SoilVoiRequest(BaseModel):
    """El README solo fija la respuesta (SoilVoiResponse). Cuerpo mínimo provisional."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    scenario_id: str = Field(default="BASE", pattern=SCENARIO_ID_PATTERN)
    adaptation_mode: AdaptationMode = AdaptationMode.none
    property_code: Literal["ph"] = "ph"


# --- Respuestas con DTO de R2 pendiente: transporte opaco, nunca valores inventados -------------
class StrategyRiskPayload(OpaqueJson):
    model_config = ConfigDict(json_schema_extra=pending("R2", "StrategyRiskDTO[] (paginado)"))


class ClimateHistoryPayload(OpaqueJson):
    model_config = ConfigDict(
        json_schema_extra=pending("R2", "historial climático (sin DTO nombrado)")
    )


class HeatmapPayload(OpaqueJson):
    model_config = ConfigDict(json_schema_extra=pending("R2", "HeatmapDTO"))


class DekadChartPayload(OpaqueJson):
    model_config = ConfigDict(json_schema_extra=pending("R2", "DekadChartDTO"))


class RankResponsePayload(OpaqueJson):
    model_config = ConfigDict(json_schema_extra=pending("R2", "RankResponse"))


class SoilVoiPayload(OpaqueJson):
    model_config = ConfigDict(json_schema_extra=pending("R2", "SoilVoiResponse"))


class SourceOut(BaseModel):
    source_id: int
    code: str
    product_name: str
    institution: str
    is_nasa: bool
    version: str | None
    url: str | None
    citation: str | None


class PeriodOut(BaseModel):
    """``Period`` del README §15 (sin estructura definida allí): inicio y fin; forma propuesta."""

    start: date | None
    end: date | None


class ProvenanceOut(BaseModel):
    """``ProvenanceInfo`` del README §15 (nombres de la especificación).

    ``ip_id``, ``indicator_code`` y ``unit`` son adiciones de R3 (identifican el registro). El
    nivel de evidencia y la regla los asignó quien escribió la fila (R1/R2); R3 solo los expone.
    ``spatial_res``/``temporal_res`` son texto libre en la especificación: R3 los formatea como
    ``"10000 m"`` y duración ISO 8601 (``"P1D"``).
    """

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    ip_id: UUID
    run_id: UUID | None
    indicator_code: str
    unit: str
    provenance: str
    evidence: str | None
    evidence_rule: str
    sources: list[SourceOut]
    dataset_version: str | None
    period: PeriodOut | None
    spatial_res: str | None
    temporal_res: str | None
    method: str
    retrieved_at: datetime | None
    missing_pct: float | None
    assumptions: list[str]
    limitations: list[str]
