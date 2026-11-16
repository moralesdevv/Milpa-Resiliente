"""Valor de la información del suelo — pH (apartado 20).

¿Podría cambiar la estrategia que queda primera según valores hipotéticos de pH?
No predice rendimiento ni afirma el pH de la parcela.
"""
from __future__ import annotations

from typing import Any

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..config import VoiConfig
from ..crops import Catalogs
from ..enums import Evidence, PropertyStatus, RankingStatus, VoiApplicability, VoiOutcome
from ..provenance import min_evidence
from . import SoilContext

HYP_LABEL = "valor hipotético, no medido"


@dataclass(frozen=True)
class Hypothetical:
    value: float
    top_strategy: str | None
    excluded: tuple[str, ...]
    label: str = HYP_LABEL
    status: str = "hipotetico"  # nunca 'medido' (T-P09)


@dataclass(frozen=True)
class VoiResult:
    property_code: str
    property_status: PropertyStatus
    applicability: VoiApplicability
    outcome: VoiOutcome | None
    lab_recommended: bool
    rationale_es: str
    hypotheticals: tuple[Hypothetical, ...] | None = None
    range_citation: str | None = None
    evidence: Evidence | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # outcome es nulo si y solo si applicability ≠ evaluable
        if (self.outcome is None) != (self.applicability is not VoiApplicability.EVALUABLE):
            raise ValueError("outcome nulo ⇔ applicability ≠ evaluable")


def hypothetical_values(soil: SoilContext, cfg: VoiConfig) -> tuple[np.ndarray, str] | None:
    ph = soil.property("ph")
    if ph.status is PropertyStatus.ESTIMADO and ph.p05 is not None and ph.p95 is not None:
        return np.linspace(ph.p05, ph.p95, cfg.n_hyp), "rango p05–p95 del producto espacial"
    if cfg.zone_ph_range is not None and cfg.zone_ph_range_citation:
        return np.linspace(cfg.zone_ph_range[0], cfg.zone_ph_range[1], cfg.n_hyp), cfg.zone_ph_range_citation
    return None


def soil_voi(soil: SoilContext, base_order: tuple[str, ...], base_status: RankingStatus, strategy_crops: dict[str, set[str]],
             catalogs: Catalogs, rerank: Callable[[float], tuple[tuple[str, ...], tuple[str, ...]]], cfg: VoiConfig) -> VoiResult:
    """``rerank(ph)`` → (orden, excluidas) con mismos pesos y misma regla de soporte común."""
    st = soil.property("ph").status
    if st is PropertyStatus.MEDIDO:
        return VoiResult("ph", st, VoiApplicability.ALREADY_MEASURED, None, False,
                         "pH medido; el análisis de valor de información no aplica")
    if base_status is RankingStatus.INSUFFICIENT or not base_order:
        return VoiResult("ph", st, VoiApplicability.NOT_APPLICABLE, None, False,
                         "No hay ranking base sobre el que evaluar sensibilidad")
    hv = hypothetical_values(soil, cfg)
    if hv is None:
        return VoiResult("ph", st, VoiApplicability.EVALUABLE, VoiOutcome.INSUFFICIENT_INFO, False,
                         "sin rango documentado para el pH")
    values, rng_cit = hv
    top_k = base_order[: cfg.top_k]
    missing = sorted({c for s in top_k for c in strategy_crops[s]
                      if c not in catalogs.ph_tolerance or not catalogs.ph_tolerance[c].citation})
    if missing:
        return VoiResult("ph", st, VoiApplicability.EVALUABLE, VoiOutcome.INSUFFICIENT_INFO, False,
                         "falta matriz de tolerancia con cita para: " + ", ".join(missing)
                         + ". Sin la matriz, un análisis de pH no permitiría concluir nada sobre el ranking.",
                         range_citation=rng_cit)
    hyps = []
    for ph in values:
        order, excluded = rerank(float(ph))
        hyps.append(Hypothetical(round(float(ph), 2), order[0] if order else None, tuple(excluded)))
    tops = {h.top_strategy for h in hyps}
    outcome = VoiOutcome.RANKING_STABLE if len(tops) == 1 else VoiOutcome.RANKING_SENSITIVE
    ev = min_evidence([catalogs.ph_tolerance[c].evidence for s in top_k for c in strategy_crops[s]] + [Evidence.C])
    why = ("La estrategia primera no cambia en el rango hipotético de pH; medirlo no cambiaría la recomendación."
           if outcome is VoiOutcome.RANKING_STABLE else
           "La estrategia primera cambia según el pH hipotético; un análisis de laboratorio podría cambiar la recomendación.")
    return VoiResult("ph", st, VoiApplicability.EVALUABLE, outcome, outcome is VoiOutcome.RANKING_SENSITIVE, why,
                     tuple(hyps), rng_cit, ev)
