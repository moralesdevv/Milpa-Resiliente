"""Matriz fecha × año (heatmap) y ventanas de siembra consistentes (apartado 11.9)."""
from __future__ import annotations

import numpy as np

from ..enums import CellState
from ..exposure import CycleResult
from ..risk import StrategyRisk, freq_pct


def heatmap_cycle(results: list[CycleResult], strategy: str, cycle_idx: int) -> dict:
    """view=cycle: eje X fecha candidata del ciclo (solo candidate_dates), eje Y año calendario de siembra."""
    rs = [r for r in results if r.strategy == strategy and r.cycle_idx == cycle_idx and r.anchor_md is not None]
    if not rs:
        raise ValueError("view=cycle solo existe para el ciclo que barre fechas candidatas")
    varieties = {r.variety for r in rs}
    if len(varieties) > 1:
        raise ValueError("los cultivos no se mezclan en una celda en la vista por ciclo")
    dates = sorted({r.anchor_md for r in rs})
    years = sorted({r.calendar_year for r in rs})
    idx = {(r.calendar_year, r.anchor_md): r for r in rs}
    state = [[(idx[(y, d)].state.value if (y, d) in idx else CellState.NOT_EVALUABLE.value) for d in dates] for y in years]
    sev = [[(idx[(y, d)].severity_mm if (y, d) in idx else None) for d in dates] for y in years]
    pct, nd = [], []
    for d in dates:
        f, n = freq_pct([idx[(y, d)].state for y in years if (y, d) in idx])
        pct.append(f)
        nd.append(n)
    return {"view": "cycle", "strategy": strategy, "cycle_idx": cycle_idx, "variety": next(iter(varieties)),
            "plant_md": dates, "years": years, "state": state, "severity_mm": sev,
            "pct_critical_by_date": pct, "n_decided_by_date": nd, "aggregation_rule": None}


def heatmap_strategy(risks: list[StrategyRisk], strategy: str) -> dict:
    """view=strategy: eje X fecha del ciclo ancla, eje Y año de inicio de la cohorte; any/sum."""
    rs = [r for r in risks if r.strategy == strategy and r.anchor_md is not None]
    if not rs:
        raise ValueError("la estrategia no barre fechas candidatas")
    dates = sorted(r.anchor_md for r in rs)
    by_d = {r.anchor_md: {c.cohort_year: c for c in r.cohorts} for r in rs}
    years = sorted({y for r in rs for y in by_d[r.anchor_md]})
    state, sev, pct, nd = [], [], [], []
    for y in years:
        state.append([(by_d[d][y].state.value if y in by_d[d] else CellState.NOT_EVALUABLE.value) for d in dates])
        sev.append([(by_d[d][y].severity_sum_mm if y in by_d[d] else None) for d in dates])
    for d in dates:
        f, n = freq_pct([c.state for c in by_d[d].values()])
        pct.append(f)
        nd.append(n)
    return {"view": "strategy", "strategy": strategy, "cycle_idx": None, "plant_md": dates, "years": years,
            "state": state, "severity_mm": sev, "pct_critical_by_date": pct, "n_decided_by_date": nd,
            "aggregation_rule": "any/sum"}


def consistent_windows(plant_md: list[str], pct_critical: list[float | None], p90: list[float | None],
                       min_dates: int = 3) -> list[tuple[str, str]]:
    """≥ min_dates fechas contiguas con frecuencia en el primer cuartil y P90 < mediana. Regla descriptiva."""
    f = np.array([np.nan if v is None else v for v in pct_critical], dtype=float)
    s = np.array([np.nan if v is None else v for v in p90], dtype=float)
    if np.all(np.isnan(f)) or np.all(np.isnan(s)):
        return []
    q1 = np.nanpercentile(f, 25)
    med = np.nanmedian(s)
    good = (f <= q1) & (s < med)
    out, run = [], []
    for i, g in enumerate(good):
        if g:
            run.append(i)
        else:
            if len(run) >= min_dates:
                out.append((plant_md[run[0]], plant_md[run[-1]]))
            run = []
    if len(run) >= min_dates:
        out.append((plant_md[run[0]], plant_md[run[-1]]))
    return out
