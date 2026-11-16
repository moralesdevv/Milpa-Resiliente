"""ESPEJO PROVISIONAL de los enums compartidos (README §15), propiedad canónica de R2.

*** ESTADO: PROVISIONAL / pendiente de R2 *** — La fuente canónica es ``milpa_core.enums``, que
todavía no existe. Este módulo existe únicamente para que la API pueda tipar parámetros y
respuestas hasta que R2 entregue el paquete (ADR-009/010). Reglas:

* No añadir miembros que no figuren en README §15 / §13.1.
* Cuando exista ``milpa_core.enums``, este módulo se sustituye por un re-export y la prueba de
  paridad (tests/contract/test_enum_parity.py) pasa a comparar contra el paquete real.
* ``window_mode_t`` existe en SQL pero NO figura en la tabla de enums compartidos del README §15:
  es un hueco de contrato registrado en docs/integration/R2_ENGINE_CONTRACT.md.
"""

from __future__ import annotations

from enum import StrEnum

ENUM_SOURCE = "provisional-readme-15"  # cambiará a "milpa_core" cuando R2 entregue


class Provenance(StrEnum):
    medido = "medido"
    satelital = "satelital"
    estimado = "estimado"
    modelado = "modelado"
    declarado = "declarado"
    desconocido = "desconocido"


class Evidence(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class PropertyStatus(StrEnum):
    medido = "medido"
    estimado = "estimado"
    declarado = "declarado"
    desconocido = "desconocido"
    desactualizado = "desactualizado"
    no_representativo = "no_representativo"
    no_disponible = "no_disponible"


class Mode(StrEnum):
    exposure = "exposure"
    root_zone = "root_zone"


class Label(StrEnum):
    indicador_exposicion_climatica = "indicador_exposicion_climatica"
    balance_hidrico_zona_radicular = "balance_hidrico_zona_radicular"


class CellState(StrEnum):
    critical = "critical"
    non_critical = "non_critical"
    insufficient_data = "insufficient_data"
    not_evaluable = "not_evaluable"


class CriterionStatus(StrEnum):
    evaluable = "evaluable"
    provisional = "provisional"
    not_evaluable = "not_evaluable"


class RankingStatus(StrEnum):
    ok = "ok"
    insufficient = "insufficient"


class StabilityFlag(StrEnum):
    stable = "stable"
    moderate = "moderate"
    unstable = "unstable"
    insufficient = "insufficient"


class VoiApplicability(StrEnum):
    evaluable = "evaluable"
    already_measured = "already_measured"
    not_applicable = "not_applicable"


class VoiOutcome(StrEnum):
    ranking_stable = "ranking_stable"
    ranking_sensitive = "ranking_sensitive"
    insufficient_info = "insufficient_info"


class AdaptationMode(StrEnum):
    none = "none"
    onset_rule = "onset_rule"


class HumidityAssumption(StrEnum):
    not_applicable = "not_applicable"
    constant_rh = "constant_rh"
    constant_ea = "constant_ea"


class StrategyAxis(StrEnum):
    association = "association"
    rotation = "rotation"
    planting_date = "planting_date"
    variety = "variety"
    cover_crop = "cover_crop"


# Tipo SQL (README §13.1) -> enum Python. None = sin enum compartido definido (hueco registrado).
SQL_TYPE_TO_ENUM: dict[str, type[StrEnum] | None] = {
    "provenance_t": Provenance,
    "evidence_t": Evidence,
    "property_status_t": PropertyStatus,
    "mode_t": Mode,
    "label_t": Label,
    "cell_state_t": CellState,
    "criterion_status_t": CriterionStatus,
    "ranking_status_t": RankingStatus,
    "stability_flag_t": StabilityFlag,
    "voi_applicability_t": VoiApplicability,
    "voi_outcome_t": VoiOutcome,
    "adaptation_t": AdaptationMode,
    "humidity_t": HumidityAssumption,
    "strategy_axis_t": StrategyAxis,
    "window_mode_t": None,
}
