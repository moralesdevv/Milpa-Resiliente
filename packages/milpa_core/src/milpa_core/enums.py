"""Única definición de estados, modos y etiquetas (principio P8, apartado 15).

R3 genera los tipos SQL y OpenAPI desde aquí (ver ``export_sql``); una prueba de
paridad compara los tres.
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmético
        return str(self.value)


class Provenance(StrEnum):
    MEDIDO = "medido"
    SATELITAL = "satelital"
    ESTIMADO = "estimado"
    MODELADO = "modelado"
    DECLARADO = "declarado"
    DESCONOCIDO = "desconocido"


class Evidence(StrEnum):
    A = "A"
    B = "B"
    C = "C"

    @property
    def rank(self) -> int:  # A=3 > B=2 > C=1
        return {"A": 3, "B": 2, "C": 1}[self.value]


class PropertyStatus(StrEnum):
    MEDIDO = "medido"
    ESTIMADO = "estimado"
    DECLARADO = "declarado"
    DESCONOCIDO = "desconocido"
    DESACTUALIZADO = "desactualizado"
    NO_REPRESENTATIVO = "no_representativo"
    NO_DISPONIBLE = "no_disponible"


class Mode(StrEnum):
    EXPOSURE = "exposure"
    ROOT_ZONE = "root_zone"


class Label(StrEnum):
    EXPOSURE_INDICATOR = "indicador_exposicion_climatica"
    ROOT_ZONE_BALANCE = "balance_hidrico_zona_radicular"


MODE_LABEL = {Mode.EXPOSURE: Label.EXPOSURE_INDICATOR, Mode.ROOT_ZONE: Label.ROOT_ZONE_BALANCE}


class CellState(StrEnum):
    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_EVALUABLE = "not_evaluable"


DECIDED = (CellState.CRITICAL, CellState.NON_CRITICAL)


class CriterionStatus(StrEnum):
    EVALUABLE = "evaluable"
    PROVISIONAL = "provisional"
    NOT_EVALUABLE = "not_evaluable"


class Criterion(StrEnum):
    WATER = "water"
    SOIL = "soil"
    FOOD = "food"
    INCOME = "income"


CRITERIA = (Criterion.WATER, Criterion.SOIL, Criterion.FOOD, Criterion.INCOME)


class RankingStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT = "insufficient"


class StabilityFlag(StrEnum):
    STABLE = "stable"
    MODERATE = "moderate"
    UNSTABLE = "unstable"
    INSUFFICIENT = "insufficient"


class VoiApplicability(StrEnum):
    EVALUABLE = "evaluable"
    ALREADY_MEASURED = "already_measured"
    NOT_APPLICABLE = "not_applicable"


class VoiOutcome(StrEnum):
    RANKING_STABLE = "ranking_stable"
    RANKING_SENSITIVE = "ranking_sensitive"
    INSUFFICIENT_INFO = "insufficient_info"


class AdaptationMode(StrEnum):
    NONE = "none"
    ONSET_RULE = "onset_rule"


class HumidityAssumption(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    CONSTANT_RH = "constant_rh"
    CONSTANT_EA = "constant_ea"


class StrategyAxis(StrEnum):
    ASSOCIATION = "association"
    ROTATION = "rotation"
    PLANTING_DATE = "planting_date"
    VARIETY = "variety"
    COVER_CROP = "cover_crop"


class WindowMode(StrEnum):
    CANDIDATE_DATES = "candidate_dates"
    FIXED_SEASON_WINDOW = "fixed_season_window"
    RELATIVE_TO_PREVIOUS_HARVEST = "relative_to_previous_harvest"


class IndicatorKind(StrEnum):
    EXPOSURE = "exposure"
    ROOT_ZONE = "root_zone"
    CLIMATE_INPUT = "climate_input"
    SOIL_PROPERTY = "soil_property"
    CRITERION = "criterion"
    RANKING = "ranking"
    ECONOMIC = "economic"


class PeffMethod(StrEnum):
    USDA_SCS_FAO = "usda_scs_fao"
    FAO_DEPENDABLE = "fao_dependable"
    FIXED_FRACTION = "fixed_fraction"
    UPPER_BOUND = "upper_bound"


MONTHLY_PEFF = (PeffMethod.USDA_SCS_FAO, PeffMethod.FAO_DEPENDABLE)


class EaMethod(StrEnum):
    DEWPOINT = "dewpoint_T2MDEW"
    RH_MEAN = "rh_mean_RH2M"
    MISSING = "missing"


class Consistency(StrEnum):
    CONSISTENTE = "consistente"
    VARIABLE = "variable"
    FALLOS_ANOS_DESFAVORABLES = "fallos_en_años_desfavorables"
    NO_COMPARABLE = "no_comparable"


class ThresholdMetric(StrEnum):
    DEKAD_EXPOSURE_MM = "dekad_exposure_mm"
    STAGE_CUM_EXPOSURE_MM = "stage_cum_exposure_mm"
    PEF_OVER_ETC_RATIO = "pef_over_etc_ratio"
    STRESS_DAYS_EQUIV = "stress_days_equiv"


class QcFlag:
    """Bits de ``qc_flags`` (apartado 13.7). Mismo significado que R1."""

    MISSING = 1
    OUT_OF_RANGE = 2
    LINEAR_FILL = 4
    BIAS_CORRECTED = 8
    RAD_MODELED = 16
    FALLBACK_SOURCE = 32


# Razones/limitaciones estandarizadas (texto estable para UI e informe)
class Reason(StrEnum):
    PROVISIONAL_SIN_CITA = "provisional_sin_cita"
    DATOS_INSUFICIENTES = "datos_insuficientes"
    EA_SENSIBLE_A_LA_RUTA = "ea_sensible_a_la_ruta"
    PEFF_SENSIBLE_AL_METODO = "peff_sensible_al_metodo"
    FENOLOGIA_FIJA_EN_DIAS = "fenologia_fija_en_dias"
    SIN_CONTINUIDAD_DE_SUELO = "sin_continuidad_de_suelo"
    SENSIBLE_A_CONDICION_INICIAL = "sensible_a_condicion_inicial"
    ESCENARIO_SENSIBLE_A_HUMEDAD = "escenario_sensible_a_humedad"
    UMBRAL_SANDBOX = "umbral provisional — no usar para decisión"


ALL_ENUMS: list[type[StrEnum]] = [
    Provenance, Evidence, PropertyStatus, Mode, Label, CellState, CriterionStatus, Criterion,
    RankingStatus, StabilityFlag, VoiApplicability, VoiOutcome, AdaptationMode,
    HumidityAssumption, StrategyAxis, WindowMode, IndicatorKind, PeffMethod, EaMethod,
    Consistency, ThresholdMetric,
]


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def export_sql() -> str:
    """DDL de tipos para la migración de R1/R3 (paridad de enums, T-C)."""
    lines: list[str] = []
    for e in ALL_ENUMS:
        vals = ", ".join(f"'{m.value}'" for m in e)
        lines.append(f"CREATE TYPE {_snake(e.__name__)}_t AS ENUM ({vals});")
    return "\n".join(lines)


def export_json() -> dict[str, list[str]]:
    return {e.__name__: [m.value for m in e] for e in ALL_ENUMS}
