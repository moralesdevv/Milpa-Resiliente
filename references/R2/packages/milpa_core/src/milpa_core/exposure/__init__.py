"""Modo A — indicador de exposición climática por ciclo (apartado 11.7).

e = max(0, ETc − Pef) por segmento (decena ∩ etapa crítica). No usa suelo.
Cada componente de una asociación se evalúa por separado; el ciclo es crítico si
algún componente lo es.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..climate.dekad import dekad_length
from ..climate.evaluability import Evaluability, window_evaluable
from ..climate.series import CuratedClimate
from ..config import RegionConfig
from ..crops import Calendar, Catalogs, Threshold
from ..enums import CellState, Evidence, Mode, Reason, ThresholdMetric
from ..provenance import min_evidence
from ..strategy import CycleInstance

LEVELS = ("central", "low", "high")


@dataclass(frozen=True)
class Segment:
    dekad_key: int
    stage: str
    critical: bool
    start: str
    n_days: int
    dekad_days: int
    etc_mm: float
    pef_mm: float
    exposure_mm: float
    limit_mm: dict  # level → valor escalado o None
    over: dict  # level → bool | None


@dataclass(frozen=True)
class ComponentExposure:
    variety: str
    crop: str
    role: str
    area_fraction: float
    severity_mm: float
    state: dict  # level → CellState
    provisional: bool
    reasons: tuple[str, ...]
    segments: tuple[Segment, ...]
    evidence: Evidence | None
    thresholds_used: tuple[dict, ...] = ()


@dataclass(frozen=True)
class CycleResult:
    strategy: str
    cohort_year: int
    cycle_idx: int
    anchor_md: str | None
    season: str
    agri_year: int
    calendar_year: int
    variety: str
    plant_date: str | None
    harvest_date: str | None
    mode: Mode
    peff_method: str
    state: CellState
    state_by_level: dict
    severity_mm: float | None
    provisional: bool
    reasons: tuple[str, ...]
    evaluability: Evaluability | None
    components: tuple[ComponentExposure, ...] = ()
    evidence: Evidence | None = None
    state_by_peff: dict = field(default_factory=dict)  # método → estado central (sensibilidad)
    stress_days: float | None = None  # Modo B
    adapted: bool = False

    @property
    def decided(self) -> bool:
        return self.state in (CellState.CRITICAL, CellState.NON_CRITICAL)


def _not_evaluable(ci: CycleInstance, mode: Mode, method: str, reason: str, ev: Evaluability | None = None) -> CycleResult:
    st = {lv: CellState.NOT_EVALUABLE for lv in LEVELS}
    return CycleResult(ci.strategy, ci.cohort_year, ci.cycle_idx, ci.anchor_md, ci.season, ci.agri_year, ci.calendar_year,
                       ci.principal_variety, None if ci.plant_date is None else str(ci.plant_date),
                       None if ci.harvest_date is None else str(ci.harvest_date), mode, method, CellState.NOT_EVALUABLE,
                       st, None, False, (reason,), ev, adapted=ci.adapted)


def cycle_evaluability(ci: CycleInstance, clim: CuratedClimate, region: RegionConfig) -> Evaluability:
    s = clim.sl(ci.plant_date, ci.harvest_date)
    b = clim.base
    met = [b.tmax_c[s], b.tmin_c[s], b.wind2m_ms[s], b.srad_mj_m2[s], clim.ea_kpa[s]]
    return window_evaluable(b.precip_mm[s], met, region.max_missing_precip_pct, region.max_missing_met_pct)


def stage_segments(cal: Calendar, clim: CuratedClimate, pef_day: np.ndarray, only_critical: bool = True) -> list[dict]:
    """Segmentos decena ∩ etapa con ETc y Pef sumadas por día (prorrateo de decenas parciales)."""
    sl = clim.sl(cal.plant_date, cal.harvest_date)
    et0 = clim.et0_mm[sl]
    pef = pef_day[sl]
    dk = clim.dekad_key[sl]
    etc_d = cal.kc * et0
    out = []
    keys = dk * 100 + cal.stage_idx
    # orden temporal preservado
    _, first = np.unique(keys, return_index=True)
    for i0 in np.sort(first):
        k = keys[i0]
        m = keys == k
        st = int(cal.stage_idx[i0])
        crit = bool(cal.critical[i0])
        if only_critical and not crit:
            continue
        dkey = int(dk[i0])
        out.append({
            "dekad_key": dkey, "stage": cal.stage_codes[st], "critical": crit,
            "start": str(cal.plant_date + np.timedelta64(int(i0), "D")), "n_days": int(m.sum()),
            "dekad_days": dekad_length(dkey // 100, dkey % 100),
            "etc_mm": float(np.sum(etc_d[m])), "pef_mm": float(np.sum(pef[m])),
        })
    return out


def _component_exposure(comp, clim: CuratedClimate, catalogs: Catalogs, method: str, min_seg: int = 1) -> ComponentExposure:
    v = comp.variety
    cal = comp.calendar
    segs_raw = stage_segments(cal, clim, clim.pef_day[method], only_critical=True)
    reasons: list[str] = []
    provisional = False
    crit_stages = v.critical_stages
    thr_ev: list[Evidence | None] = []
    thresholds_used = []
    if not crit_stages:
        reasons.append("sin_ventana_critica_en_catalogo")
    for s in crit_stages:
        if not s.cited:
            provisional = True
            if Reason.PROVISIONAL_SIN_CITA.value not in reasons:
                reasons.append(Reason.PROVISIONAL_SIN_CITA.value)
    thr: dict[str, Threshold | None] = {s.code: catalogs.threshold(v.crop, s.code, method) for s in crit_stages}
    missing_thr = [k for k, t in thr.items() if t is None]
    for k, t in thr.items():
        if t is None:
            continue
        thr_ev.append(t.evidence if t.cited else Evidence.C)
        if not t.cited:
            provisional = True
            if Reason.UMBRAL_SANDBOX.value not in reasons:
                reasons.append(Reason.UMBRAL_SANDBOX.value)
        thresholds_used.append({"crop": t.crop, "stage": t.stage, "metric": t.metric.value, "value": t.value,
                                "sens_low": t.sens_low, "sens_high": t.sens_high, "unit": t.unit,
                                "peff_method": None if t.peff_method is None else str(t.peff_method),
                                "citation": t.citation, "provisional": not t.cited})
    segments = []
    stage_over: dict[str, dict] = {}
    for sr in segs_raw:
        e = max(0.0, sr["etc_mm"] - sr["pef_mm"])
        t = thr.get(sr["stage"])
        limit, over = {}, {}
        for lv in LEVELS:
            val = None if t is None else (t.at(lv) if t.at(lv) is not None else t.value)
            if t is not None and t.metric is ThresholdMetric.DEKAD_EXPOSURE_MM and val is not None and sr["n_days"] >= min_seg:
                limit[lv] = val * sr["n_days"] / sr["dekad_days"]
                over[lv] = e > limit[lv]
            else:
                limit[lv], over[lv] = None, None
        segments.append(Segment(sr["dekad_key"], sr["stage"], sr["critical"], sr["start"], sr["n_days"], sr["dekad_days"],
                                sr["etc_mm"], sr["pef_mm"], e, limit, over))
    # métricas por etapa
    for s in crit_stages:
        t = thr.get(s.code)
        if t is None or t.metric is ThresholdMetric.DEKAD_EXPOSURE_MM:
            continue
        seg_s = [g for g in segments if g.stage == s.code]
        etc = sum(g.etc_mm for g in seg_s)
        pef = sum(g.pef_mm for g in seg_s)
        cum = sum(g.exposure_mm for g in seg_s)
        so = {}
        for lv in LEVELS:
            val = t.at(lv) if t.at(lv) is not None else t.value
            if t.metric is ThresholdMetric.STAGE_CUM_EXPOSURE_MM:
                so[lv] = cum > val
            elif t.metric is ThresholdMetric.PEF_OVER_ETC_RATIO:
                so[lv] = (pef / etc) < val if etc > 0 else False
            else:
                so[lv] = None
        stage_over[s.code] = so
    severity = float(sum(g.exposure_mm for g in segments))
    state = {}
    for lv in LEVELS:
        flags = [g.over[lv] for g in segments if g.over[lv] is not None] + [so[lv] for so in stage_over.values() if so[lv] is not None]
        if any(flags):
            state[lv] = CellState.CRITICAL
        elif missing_thr or not crit_stages:
            state[lv] = CellState.INSUFFICIENT_DATA
        else:
            state[lv] = CellState.NON_CRITICAL
    if missing_thr and Reason.PROVISIONAL_SIN_CITA.value not in reasons:
        reasons.append(Reason.PROVISIONAL_SIN_CITA.value)
    if missing_thr:
        reasons.append("sin_umbral:" + ",".join(missing_thr))
    ev = min_evidence([clim.base.precip_prov.evidence, clim.et0_prov.evidence, clim.pef_prov[method].evidence,
                       v.kc_evidence] + (thr_ev or [Evidence.C]))
    if provisional and ev is not None:
        ev = Evidence.C
    return ComponentExposure(v.code, v.crop, comp.component.role, comp.component.area_fraction, severity, state,
                             provisional, tuple(reasons), tuple(segments), ev, tuple(thresholds_used))


def evaluate_cycle_exposure(ci: CycleInstance, clim: CuratedClimate, catalogs: Catalogs, region: RegionConfig,
                            method: str | None = None, with_peff_sensitivity: bool = True) -> CycleResult:
    method = str(method or region.primary_peff.value)
    if ci.invalid_reason or ci.plant_date is None or ci.harvest_date is None:
        return _not_evaluable(ci, Mode.EXPOSURE, method, ci.invalid_reason or "fechas_no_calculables")
    if not clim.covers(ci.plant_date, ci.harvest_date):
        return _not_evaluable(ci, Mode.EXPOSURE, method, "fuera_de_la_ventana_de_datos")
    ev = cycle_evaluability(ci, clim, region)
    if not ev.ok:
        return _not_evaluable(ci, Mode.EXPOSURE, method, "cobertura_insuficiente", ev)
    if method not in clim.pef_day:
        raise ValueError(f"método de Pef {method} no calculado en la serie")
    comps = [_component_exposure(c, clim, catalogs, method, region.min_segment_days) for c in ci.components]
    # Pef de un mes con lluvia faltante es NaN → el ciclo no es evaluable (T-P04)
    if any(not np.isfinite(g.pef_mm) for c in comps for g in c.segments):
        return _not_evaluable(ci, Mode.EXPOSURE, method, "pef_nan_por_faltantes", ev)
    state_by_level = {}
    for lv in LEVELS:
        sts = [c.state[lv] for c in comps]
        state_by_level[lv] = (CellState.CRITICAL if CellState.CRITICAL in sts else
                              CellState.INSUFFICIENT_DATA if CellState.INSUFFICIENT_DATA in sts else CellState.NON_CRITICAL)
    reasons = tuple(dict.fromkeys(r for c in comps for r in c.reasons))
    provisional = any(c.provisional for c in comps)
    severity = max(c.severity_mm for c in comps) if comps else None
    evid = min_evidence([c.evidence for c in comps])
    by_peff = {}
    if with_peff_sensitivity:
        for m in clim.pef_day:
            if m == method:
                by_peff[m] = state_by_level["central"]
                continue
            alt = evaluate_cycle_exposure(ci, clim, catalogs, region, m, with_peff_sensitivity=False)
            by_peff[m] = alt.state
    return CycleResult(ci.strategy, ci.cohort_year, ci.cycle_idx, ci.anchor_md, ci.season, ci.agri_year, ci.calendar_year,
                       ci.principal_variety, str(ci.plant_date), str(ci.harvest_date), Mode.EXPOSURE, method,
                       state_by_level["central"], state_by_level, severity, provisional, reasons, ev, tuple(comps), evid,
                       by_peff, adapted=ci.adapted)


def dekad_chart(ci: CycleInstance, clim: CuratedClimate, catalogs: Catalogs, region: RegionConfig, method: str | None = None) -> dict:
    """Payload del gráfico por decena (DekadChartDTO, sin envoltura Indicator: la añade report/serialize)."""
    from ..crops import system_etc_exploratory

    method = str(method or region.primary_peff.value)
    res = evaluate_cycle_exposure(ci, clim, catalogs, region, method, with_peff_sensitivity=False)
    comp0 = ci.components[0]
    cal = comp0.calendar
    allseg = stage_segments(cal, clim, clim.pef_day[method], only_critical=False)
    crit_over = {(g.dekad_key, g.stage): g for c in res.components[:1] for g in c.segments}
    dekads = {}
    for s in allseg:
        d = dekads.setdefault(s["dekad_key"], {"dekad_key": s["dekad_key"], "start": s["start"], "n_days": 0,
                                               "etc_mm": 0.0, "pef_mm": 0.0, "critical_stage": None, "over_threshold": None,
                                               "limit_mm": None, "critical_segment_exposure_mm": None})
        d["n_days"] += s["n_days"]
        d["etc_mm"] += s["etc_mm"]
        d["pef_mm"] += s["pef_mm"]
        g = crit_over.get((s["dekad_key"], s["stage"]))
        if g is not None:
            d["critical_stage"] = s["stage"]
            d["over_threshold"] = bool(g.over["central"]) if g.over["central"] is not None else None
            d["limit_mm"] = g.limit_mm["central"]  # escalado a los días de etapa crítica dentro de la decena
            d["critical_segment_exposure_mm"] = g.exposure_mm  # lo que se compara con limit_mm
    sl = clim.sl(cal.plant_date, cal.harvest_date)
    p_obs = clim.precip_mm[sl]
    dk = clim.dekad_key[sl]
    out = []
    for i, (k, d) in enumerate(dekads.items()):
        d["exposure_mm"] = max(0.0, d["etc_mm"] - d["pef_mm"])
        d["p_observed_mm"] = float(np.nansum(p_obs[dk == k]))
        d["idx"] = i + 1
        out.append(d)
    etc_sys = None
    if len(ci.components) > 1:
        n = cal.n_days
        et0 = clim.et0_mm[sl]
        comps = []
        for c in ci.components:
            off = int((c.plant_date - cal.plant_date).astype(int))
            kc = np.zeros(n)
            kk = c.calendar.kc[: max(0, n - off)]
            kc[off: off + kk.size] = kk
            comps.append((c.component.area_fraction, kc))
        sysd = system_etc_exploratory(comps, et0)
        etc_sys = [float(np.sum(sysd[dk == k])) for k in dekads]
    cum, acc_e, acc_p = [], 0.0, 0.0
    for d in out:
        acc_e += d["etc_mm"]
        acc_p += d["pef_mm"]
        cum.append({"dekad_key": d["dekad_key"], "etc_cum_mm": acc_e, "pef_cum_mm": acc_p})
    return {
        "strategy": ci.strategy, "cohort_year": ci.cohort_year, "cycle_idx": ci.cycle_idx, "plant_date": str(ci.plant_date),
        "harvest_date": str(ci.harvest_date), "variety": comp0.variety.code, "peff_method": method,
        "state": res.state.value, "severity_mm": res.severity_mm, "provisional": res.provisional, "reasons": list(res.reasons),
        "dekads": out, "stage_bands": cal.stage_bands(), "etc_system_exploratory": etc_sys,
        "etc_system_label": "aproximación exploratoria" if etc_sys else None, "cumulative": cum,
    }
