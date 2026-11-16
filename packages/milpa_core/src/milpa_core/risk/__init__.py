"""Agregación robusta por ciclo y por estrategia (apartados 11.6 y 11.9).

Unidad de análisis explícita: ciclo-instancia (estrategia, cohorte, cycle_idx) y
cohorte (estrategia, año de inicio) con lógica trivalente. Un ciclo not_evaluable
no entra en percentiles ni frecuencias; reduce n_valid (T-P07).
"""
from __future__ import annotations

from typing import Any

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..config import RiskConfig
from ..enums import CellState, Consistency, Evidence, Reason
from ..exposure import CycleResult
from ..provenance import min_evidence
from ..strategy import n_independent_cohorts


def _p(a, q):
    a = np.asarray(a, dtype=float)
    return float(np.percentile(a, q)) if a.size else None


def severity_stats(sev: list[float], years: list[int], eps: float = 1e-6) -> dict[str, Any]:
    if not sev:
        return {"severity_median_mm": None, "severity_p90_mm": None, "severity_cvar90_mm": None,
                "worst_year": None, "worst_year_severity_mm": None, "tail_ratio": None}
    a = np.asarray(sev, dtype=float)
    p90 = _p(a, 90)
    med = _p(a, 50)
    tail = a[a >= p90 - 1e-12]
    iw = int(np.argmax(a))
    return {"severity_median_mm": med, "severity_p90_mm": p90, "severity_cvar90_mm": float(tail.mean()),
            "worst_year": int(years[iw]), "worst_year_severity_mm": float(a[iw]), "tail_ratio": p90 / max(med, eps)}


def freq_pct(states: list[CellState]) -> tuple[float | None, int]:
    dec = [s for s in states if s in (CellState.CRITICAL, CellState.NON_CRITICAL)]
    if not dec:
        return None, 0
    return 100.0 * sum(s is CellState.CRITICAL for s in dec) / len(dec), len(dec)


@dataclass(frozen=True)
class CycleRisk:
    strategy: str
    cycle_idx: int
    variety: str
    anchor_md: str | None
    freq_critical_pct: float | None
    n_decided: int
    n_valid: int
    n_expected: int
    stats: dict[str, Any]
    threshold_sensitivity: dict[str, Any]
    peff_sensitivity: dict[str, Any]
    flags: tuple[str, ...]
    provisional: bool
    evidence: Evidence | None
    reasons: tuple[str, ...] = ()

    @property
    def insufficient(self) -> bool:
        return Reason.DATOS_INSUFICIENTES.value in self.flags


@dataclass(frozen=True)
class CohortResult:
    strategy: str
    cohort_year: int
    anchor_md: str | None
    state: CellState
    severity_sum_mm: float | None
    n_cycles_decided: int
    states_by_cycle: tuple[str, ...]
    all_evaluable: bool


@dataclass(frozen=True)
class StrategyRisk:
    strategy: str
    anchor_md: str | None
    horizon_years: int
    overlapping_cohorts: bool
    n_independent_cohorts: int
    cohorts: tuple[CohortResult, ...]
    cohort_freq_critical_pct: float | None
    n_decided: int
    n_undecided: int
    pooled_critical_share_pct: float | None  # (a) invariante al horizonte
    p90_severity_by_agri_year_mm: float | None  # (b)
    tail_ratio: float | None  # (c)
    by_cycle: tuple[CycleRisk, ...]
    provisional: bool
    evidence: Evidence | None
    flags: tuple[str, ...]
    consistency: Consistency = Consistency.NO_COMPARABLE
    by_year_crit: dict[str, Any] = field(default_factory=dict)  # agri_year → (n_crit, n_decided) para bootstrap

    @property
    def insufficient(self) -> bool:
        return Reason.DATOS_INSUFICIENTES.value in self.flags


def aggregate_cycle(results: list[CycleResult], cfg: RiskConfig, comm_tol_pct: float = 10.0) -> list[CycleRisk]:
    groups: dict[tuple, list[CycleResult]] = defaultdict(list)
    for r in results:
        groups[(r.strategy, r.cycle_idx, r.anchor_md)].append(r)
    out = []
    for (s, ci, a), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
        valid = [r for r in rs if r.state is not CellState.NOT_EVALUABLE]
        f, nd = freq_pct([r.state for r in rs])
        sev = [r.severity_mm for r in valid if r.severity_mm is not None]
        yrs = [r.calendar_year for r in valid if r.severity_mm is not None]
        stats = severity_stats(sev, yrs, cfg.eps)
        ts = {lv: freq_pct([r.state_by_level[lv] for r in rs])[0] for lv in ("low", "central", "high")}
        methods = sorted({m for r in valid for m in r.state_by_peff})
        ps = {m: freq_pct([r.state_by_peff.get(m, CellState.NOT_EVALUABLE) for r in valid])[0] for m in methods}
        flags = []
        if len(valid) < cfg.min_valid_years:
            flags.append(Reason.DATOS_INSUFICIENTES.value)
        vals = [v for v in ps.values() if v is not None]
        if len(vals) > 1 and (max(vals) - min(vals)) > comm_tol_pct:
            flags.append(Reason.PEFF_SENSIBLE_AL_METODO.value)
        tsv = [v for v in ts.values() if v is not None]
        if len(tsv) > 1 and (max(tsv) - min(tsv)) > comm_tol_pct:
            flags.append("sensible_al_umbral")
        reasons = tuple(dict.fromkeys(x for r in rs for x in r.reasons))
        out.append(CycleRisk(s, ci, rs[0].variety, a, f, nd, len(valid), len(rs), stats, ts, ps, tuple(flags),
                             any(r.provisional for r in valid), min_evidence([r.evidence for r in valid]) if valid else None,
                             reasons))
    return out


def cohort_state(states: list[CellState]) -> CellState:
    if CellState.CRITICAL in states:
        return CellState.CRITICAL
    if states and all(s is CellState.NON_CRITICAL for s in states):
        return CellState.NON_CRITICAL
    if all(s is CellState.NOT_EVALUABLE for s in states):
        return CellState.NOT_EVALUABLE
    return CellState.INSUFFICIENT_DATA


def aggregate_strategy(results: list[CycleResult], cfg: RiskConfig, horizons: dict[str, int],
                       cycle_risk: list[CycleRisk] | None = None, comm_tol_pct: float = 10.0) -> list[StrategyRisk]:
    cycle_risk = cycle_risk if cycle_risk is not None else aggregate_cycle(results, cfg, comm_tol_pct)
    by_sa: dict[tuple, list[CycleResult]] = defaultdict(list)
    for r in results:
        by_sa[(r.strategy, r.anchor_md)].append(r)  # todos los ciclos de una cohorte comparten anchor_md
    out = []
    for (s, a), rs in sorted(by_sa.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        by_c: dict[int, list[CycleResult]] = defaultdict(list)
        for r in rs:
            by_c[r.cohort_year].append(r)
        cohorts = []
        sev_by_ay: list[float] = []
        by_year: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        for y, cs in sorted(by_c.items()):
            cs = sorted(cs, key=lambda r: r.cycle_idx)
            st = cohort_state([r.state for r in cs])
            all_ev = all(r.state is not CellState.NOT_EVALUABLE for r in cs)
            sev_sum = float(sum(r.severity_mm or 0.0 for r in cs)) if all_ev else None
            cohorts.append(CohortResult(s, y, a, st, sev_sum, sum(r.decided for r in cs),
                                        tuple(r.state.value for r in cs), all_ev))
            if all_ev:
                ay: dict[int, float] = defaultdict(float)
                for r in cs:
                    ay[r.agri_year] += r.severity_mm or 0.0
                sev_by_ay += list(ay.values())
            for r in cs:
                if r.decided:
                    by_year[r.agri_year][1] += 1
                    by_year[r.agri_year][0] += int(r.state is CellState.CRITICAL)
        f, nd = freq_pct([c.state for c in cohorts])
        nund = len(cohorts) - nd
        dec_cycles = [r for r in rs if r.decided]
        pooled = 100.0 * sum(r.state is CellState.CRITICAL for r in dec_cycles) / len(dec_cycles) if dec_cycles else None
        p90 = _p(sev_by_ay, 90) if sev_by_ay else None
        med = _p(sev_by_ay, 50) if sev_by_ay else None
        tail = (p90 / max(med, cfg.eps)) if p90 is not None else None
        h = horizons.get(s, 1)
        n_years = len({c.cohort_year for c in cohorts}) + h - 1
        flags = []
        n_valid = sum(c.all_evaluable for c in cohorts)
        if n_valid < cfg.min_valid_years:
            flags.append(Reason.DATOS_INSUFICIENTES.value)
        if h > 1:
            flags.append("frecuencia_por_cohorte_dependiente_del_horizonte")
        crs = tuple(c for c in cycle_risk if c.strategy == s and c.anchor_md == a)
        ev = min_evidence([r.evidence for r in rs if r.state is not CellState.NOT_EVALUABLE]) if n_valid else None
        out.append(StrategyRisk(s, a, h, h > 1, n_independent_cohorts(n_years, h), tuple(cohorts), f, nd, nund, pooled,
                                p90, tail, crs, any(r.provisional for r in rs), ev, tuple(flags),
                                by_year_crit={k: tuple(v) for k, v in by_year.items()}))
    return out


def assign_consistency(risks: list[StrategyRisk]) -> list[StrategyRisk]:
    """Etiqueta relativa por terciles de tail_ratio y frecuencia (≥ 3 estrategias comparables).

    Regla declarada [Propuesto R2]: tercil superior de cola → fallos_en_años_desfavorables;
    si no, tercil superior de frecuencia → variable; si no, consistente.
    """
    from dataclasses import replace

    comp = [r for r in risks if not r.insufficient and r.tail_ratio is not None and r.pooled_critical_share_pct is not None]
    if len(comp) < 3:
        return [replace(r, consistency=Consistency.NO_COMPARABLE) for r in risks]
    t_hi = np.percentile([r.tail_ratio for r in comp], 200 / 3)
    f_hi = np.percentile([r.pooled_critical_share_pct for r in comp], 200 / 3)
    out = []
    for r in risks:
        if r not in comp:
            out.append(replace(r, consistency=Consistency.NO_COMPARABLE))
        elif r.tail_ratio > t_hi:
            out.append(replace(r, consistency=Consistency.FALLOS_ANOS_DESFAVORABLES))
        elif r.pooled_critical_share_pct > f_hi:
            out.append(replace(r, consistency=Consistency.VARIABLE))
        else:
            out.append(replace(r, consistency=Consistency.CONSISTENTE))
    return out
