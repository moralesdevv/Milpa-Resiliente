"""Payloads con forma de DTO (apartado 15): todo número visible viaja en un Indicator.

R3 define los modelos pydantic sobre estas estructuras; los nombres de campo coinciden
con CycleRiskDTO, StrategyRiskDTO, HeatmapDTO, DekadChartDTO, RankResponse y SoilVoiResponse.
"""
from __future__ import annotations

from typing import Any

from .enums import MODE_LABEL, Evidence, IndicatorKind, Mode, Provenance
from .facade import ScenarioRunResult
from .provenance import IndicatorBuilder, ProvenanceInfo
from .ranking import RankingResult, StabilityResult
from .risk import CycleRisk, StrategyRisk
from .serialize import to_jsonable


def _risk_prov(run: ScenarioRunResult, evidence: Evidence | None, rule: str) -> ProvenanceInfo:
    c = run.climate
    return ProvenanceInfo(
        provenance=Provenance.MODELADO if evidence is not None else Provenance.DESCONOCIDO, evidence=evidence,
        evidence_rule=rule,
        method=f"{MODE_LABEL[run.decision.mode].value}; Pef={run.meta['peff_primary']}; ET0=FAO56-PM",
        sources=c.base.precip_prov.sources + c.base.met_prov.sources, assumptions=c.et0_prov.assumptions,
        limitations=tuple(run.limitations) + c.et0_prov.limitations, run_id=str(run.meta.get("run_id")),
    )


def _ind(run, code, es, en, value, unit, evidence, provisional, reason=None, kind=None):
    mode = run.decision.mode
    kind = kind or (IndicatorKind.EXPOSURE if mode is Mode.EXPOSURE else IndicatorKind.ROOT_ZONE)
    label = MODE_LABEL[mode] if kind in (IndicatorKind.EXPOSURE, IndicatorKind.ROOT_ZONE) else None
    b = IndicatorBuilder(code, es, en, unit, kind, label)
    b.from_inputs(_risk_prov(run, evidence, "risk.min_lluvia_et0_kc_umbral")).rule("risk.min_lluvia_et0_kc_umbral")
    b.method(_risk_prov(run, evidence, "x").method)
    tag = None if run.scenario.is_base else run.tag
    return to_jsonable(b.build(value, provisional=provisional,
                               reason=(reason or "umbral provisional — no usar para decisión") if provisional else None,
                               scenario=tag))


def cycle_risk_dto(run: ScenarioRunResult, c: CycleRisk) -> dict[str, Any]:
    st = c.stats
    sev_unit = "mm" if run.decision.mode is Mode.EXPOSURE else "días-equivalentes"
    p = c.provisional
    return {
        "strategy": c.strategy, "cycle_idx": c.cycle_idx, "variety": c.variety, "anchor_md": c.anchor_md,
        "freq_critical": _ind(run, "freq_critical_pct", "Frecuencia de ciclos críticos", "Critical cycle frequency",
                              c.freq_critical_pct, "%", c.evidence, p),
        "severity_median": _ind(run, "severity_median_mm", "Mediana de severidad", "Severity median", st["severity_median_mm"], sev_unit, c.evidence, p),
        "severity_p90": _ind(run, "severity_p90_mm", "P90 de severidad", "Severity P90", st["severity_p90_mm"], sev_unit, c.evidence, p),
        "severity_cvar90": _ind(run, "severity_cvar90_mm", "CVaR90 de severidad (descriptivo)", "Severity CVaR90 (descriptive)",
                                st["severity_cvar90_mm"], sev_unit, c.evidence, p),
        "worst_year": _ind(run, "worst_year", "Año más severo", "Worst year", st["worst_year"], "año", c.evidence, p),
        "worst_year_severity": _ind(run, "worst_year_severity_mm", "Severidad del peor año", "Worst-year severity",
                                    st["worst_year_severity_mm"], sev_unit, c.evidence, p),
        "coverage": {"n_valid": c.n_valid, "n_expected": c.n_expected, "n_decided": c.n_decided},
        "threshold_sensitivity": c.threshold_sensitivity, "peff_sensitivity": c.peff_sensitivity,
        "flags": list(c.flags), "reasons": list(c.reasons),
    }


def strategy_risk_dto(run: ScenarioRunResult, r: StrategyRisk, name: str, changes: list[str]) -> dict[str, Any]:
    p = r.provisional
    return {
        "strategy": r.strategy, "name": name, "anchor_md": r.anchor_md, "changes_from_reference": changes,
        "horizon_years": r.horizon_years, "overlapping_cohorts": r.overlapping_cohorts,
        "n_independent_cohorts": r.n_independent_cohorts,
        "cohort_freq_critical": _ind(run, "cohort_freq_critical_pct", "Frecuencia de cohortes críticas (depende del horizonte)",
                                     "Critical cohort frequency (horizon-dependent)", r.cohort_freq_critical_pct, "%", r.evidence, p),
        "n_decided": r.n_decided, "n_undecided": r.n_undecided,
        "water_inputs": {
            "pooled_critical_share": _ind(run, "pooled_critical_share_pct", "Proporción de ciclos críticos (agrupada)",
                                          "Pooled critical cycle share", r.pooled_critical_share_pct, "%", r.evidence, p),
            "p90_severity_by_agri_year": _ind(run, "p90_severity_by_agri_year_mm", "P90 de severidad por año agrícola",
                                              "P90 severity per agricultural year", r.p90_severity_by_agri_year_mm, "mm", r.evidence, p),
            "tail_ratio": _ind(run, "tail_ratio", "Cociente de cola", "Tail ratio", r.tail_ratio, "adimensional", r.evidence, p),
        },
        "cohorts": to_jsonable(r.cohorts),
        "by_cycle": [cycle_risk_dto(run, c) for c in r.by_cycle],
        "consistency": r.consistency.value, "flags": list(r.flags),
    }


def run_summary_dto(run: ScenarioRunResult, strategies) -> dict[str, Any]:
    names = {s.code: (s.name, [a.value for a in s.changes_from_reference]) for s in strategies}
    return {
        "scenario": to_jsonable(run.tag), "adaptation_mode": run.adaptation.value,
        "mode": run.decision.mode.value, "label": run.decision.label.value, "mode_reasons": list(run.decision.reasons),
        "limitations": list(run.limitations), "meta": to_jsonable(run.meta),
        "strategies": [strategy_risk_dto(run, r, *names[r.strategy]) for r in run.strategy_risk],
    }


def rank_response_dto(r: RankingResult, stab: StabilityResult, extra: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for i, s in enumerate(r.order):
        cells = {}
        for c, cv in extra["criteria"][s].items():
            cells[c.value] = {"status": cv.status.value, "value": cv.value, "unit": cv.unit,
                              "evidence": None if cv.evidence is None else cv.evidence.value,
                              "normalised": r.scores.get(c, {}).get(s), "subindicators": to_jsonable(cv.subindicators),
                              "reason": cv.reason}
        rows.append({"rank": i + 1, "strategy": s, "total": r.totals[s], "criteria": cells})
    return {
        "status": r.status.value, "criteria_used": [c.value for c in r.criteria_used],
        "weights": to_jsonable(r.weights), "weights_effective": to_jsonable(r.weights_effective) or None,
        "weight_coverage": r.weight_coverage, "ranking": rows, "partial_table": to_jsonable(r.partial_table),
        "top_margin": r.top_margin, "margin_within_uncertainty": r.margin_within_uncertainty,
        "evidence": None if r.evidence is None else r.evidence.value, "provisional": r.provisional,
        "decision_log": to_jsonable(r.decision_log), "explanations": to_jsonable(r.explanations),
        "ties": to_jsonable(r.ties), "message": r.message,
        "stability": {"flag": stab.flag.value, "top1_share": stab.top1_share, "rank_corr_mean": stab.rank_corr_mean,
                      "conflicts": to_jsonable(stab.conflicts), "interpretation_es": stab.interpretation_es,
                      "n_samples": stab.n_samples, "seed": stab.seed, "mode": stab.mode},
    }
