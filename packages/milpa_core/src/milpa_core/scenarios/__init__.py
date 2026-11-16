"""Escenarios sintéticos: perturbaciones deterministas de la serie curada (apartado 19).

No es pronóstico ni proyección. Orden fijo: (1) retraso de inicio de lluvias →
(2) escalado de P → (3) ΔT con supuesto de humedad → (4) recálculo de ET0 y Pef.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

import numpy as np

from ..climate.et0 import es_from
from ..climate.series import ClimateSeries, CuratedClimate, derive_climate
from ..config import OnsetDef, RegionConfig
from ..enums import AdaptationMode, Evidence, HumidityAssumption
from ..errors import ScenarioNotApplicable
from ..provenance import ScenarioTag, cap_evidence

ENGINE_VERSION = "milpa_core 0.1.0"
METHOD_DOC = "docs/METHODS.md#escenarios"


@dataclass(frozen=True)
class ScenarioDef:
    scenario_id: str
    delta_t_c: float = 0.0
    precip_factor: float = 1.0
    onset_delay_days: int = 0
    humidity: HumidityAssumption = HumidityAssumption.NOT_APPLICABLE
    grid_role: str = "baseline"
    method_doc: str = METHOD_DOC

    def __post_init__(self) -> None:
        if (self.delta_t_c == 0) != (self.humidity is HumidityAssumption.NOT_APPLICABLE):
            raise ValueError("ΔT = 0 ⇔ humidity_assumption = not_applicable")

    @property
    def is_base(self) -> bool:
        return self.delta_t_c == 0 and self.precip_factor == 1.0 and self.onset_delay_days == 0

    def tag(self, adaptation: AdaptationMode) -> ScenarioTag:
        return ScenarioTag(self.scenario_id, self.delta_t_c, self.precip_factor, self.onset_delay_days, self.humidity,
                           adaptation, self.method_doc, ENGINE_VERSION, datetime.now(timezone.utc).isoformat(timespec="seconds"))


BASE = ScenarioDef("BASE")
_H = {HumidityAssumption.NOT_APPLICABLE: "na", HumidityAssumption.CONSTANT_RH: "rh", HumidityAssumption.CONSTANT_EA: "ea"}


def scenario_id(dt: float, pf: float, delay: int, h: HumidityAssumption) -> str:
    if dt == 0 and pf == 1.0 and delay == 0:
        return "BASE"
    p = int(round((pf - 1.0) * 100))
    return f"T+{int(dt)}_P{'+' if p >= 0 else '-'}{abs(p)}_D+{delay}_H{_H[h]}"


def standard_grid(include_humidity_sensitivity: bool = True, include_delays: bool = True) -> list[ScenarioDef]:
    """27 de la grilla estándar (1 base + 8 + 18 con constant_rh) + 18 de sensibilidad (constant_ea) = 45."""
    out = []
    delays = (0, 10, 20) if include_delays else (0,)
    for dt in (0, 1, 2):
        for pf in (1.0, 0.9, 0.8):
            for d in delays:
                if dt == 0:
                    h = HumidityAssumption.NOT_APPLICABLE
                    role = "baseline" if (pf == 1.0 and d == 0) else "primary_grid"
                    out.append(ScenarioDef(scenario_id(dt, pf, d, h), dt, pf, d, h, role))
                else:
                    h = HumidityAssumption.CONSTANT_RH
                    out.append(ScenarioDef(scenario_id(dt, pf, d, h), dt, pf, d, h, "primary_grid"))
    if include_humidity_sensitivity:
        for dt in (1, 2):
            for pf in (1.0, 0.9, 0.8):
                for d in delays:
                    h = HumidityAssumption.CONSTANT_EA
                    out.append(ScenarioDef(scenario_id(dt, pf, d, h), dt, pf, d, h, "humidity_sensitivity"))
    return out


# ------------------------------------------------------------------ inicio de lluvias

def detect_onset(p: np.ndarray, search_from: int, od: OnsetDef) -> int | None:
    """Primer día t ≥ search_from con Σ P[t:t+N] ≥ X y sin racha seca > Y días en los Z siguientes."""
    p = np.asarray(p, dtype=float)
    n = p.size
    for t in range(search_from, n - od.n_days - od.z_days):
        w = p[t:t + od.n_days]
        if not np.all(np.isfinite(w)) or w[0] < od.dry_day_mm or w.sum() < od.x_mm:  # el día de inicio es húmedo
            continue
        z = p[t:t + od.z_days]
        if not np.all(np.isfinite(z)):
            continue
        dry = z < od.dry_day_mm
        run = best = 0
        for x in dry:
            run = run + 1 if x else 0
            best = max(best, run)
        if best <= od.y_days:
            return t
    return None


def delay_rain_onset(p: np.ndarray, t0: int, delta: int) -> tuple[np.ndarray, float]:
    p = np.asarray(p, dtype=float)
    n = len(p)
    if delta == 0:
        return p.copy(), 0.0
    if t0 + delta >= n:
        raise ScenarioNotApplicable("el retraso excede la serie del año agrícola")
    out = np.empty_like(p)
    out[:t0] = p[:t0]
    out[t0:t0 + delta] = 0.0
    out[t0 + delta:] = p[t0:n - delta]  # los NaN viajan con su evento
    mass_dropped = float(np.nansum(p[n - delta:]))
    return out, mass_dropped


def agri_year_slices(dates: np.ndarray, region: RegionConfig) -> dict[int, slice]:
    out = {}
    d0, d1 = dates[0], dates[-1]
    for y in range(region.start_year - 1, region.end_year + 1):
        a = np.datetime64(f"{y:04d}-{region.agri_year_start}", "D")
        b = np.datetime64(f"{y + 1:04d}-{region.agri_year_start}", "D")
        if b <= d0 or a > d1:
            continue
        i0 = max(0, int((a - d0).astype(int)))
        i1 = min(len(dates), int((b - d0).astype(int)))
        out[y] = slice(i0, i1)
    return out


def onset_by_agri_year(dates: np.ndarray, p: np.ndarray, region: RegionConfig) -> dict[int, int | None]:
    od = region.onset
    if od is None:
        return {}
    res = {}
    for y, sl in agri_year_slices(dates, region).items():
        s0 = np.datetime64(f"{y:04d}-{od.search_start_md}", "D") if od.search_start_md >= region.agri_year_start \
            else np.datetime64(f"{y + 1:04d}-{od.search_start_md}", "D")
        rel = int((s0 - dates[sl.start]).astype(int))
        t = detect_onset(p[sl], max(rel, 0), od) if rel < (sl.stop - sl.start) else None
        res[y] = None if t is None else sl.start + t
    return res


# ------------------------------------------------------------------ perturbaciones

def scale_precip(p: np.ndarray, factor: float) -> np.ndarray:
    return np.asarray(p, dtype=float) * factor  # NaN sigue siendo NaN


def perturb_temperature(s: ClimateSeries, base: CuratedClimate, dT: float, humidity: HumidityAssumption) -> ClimateSeries:
    if dT == 0:
        return s
    es0 = es_from(s.tmax_c, s.tmin_c)
    ea0 = np.asarray(base.ea_kpa, dtype=float)
    tmax, tmin = s.tmax_c + dT, s.tmin_c + dT
    es1 = es_from(tmax, tmin)
    if humidity is HumidityAssumption.CONSTANT_EA:
        ea1 = ea0
    else:
        ea1 = (ea0 / es0) * es1
    ea1 = np.minimum(ea1, es1)
    rh1 = 100.0 * ea1 / es1  # se expresa como RH para que ET0 use exactamente ea1
    return replace(s, tmax_c=tmax, tmin_c=tmin, tdew_c=None, rh_pct=rh1)


def apply_scenario(s: ClimateSeries, base: CuratedClimate, sc: ScenarioDef, region: RegionConfig) -> CuratedClimate:
    if sc.is_base:
        return base
    p = np.array(s.precip_mm, dtype=float)
    dropped = 0.0
    onset_idx: dict[int, int] = {}
    if sc.onset_delay_days:
        if not region.delay_scenarios_enabled:
            raise ScenarioNotApplicable("escenarios de retraso deshabilitados: inicio de lluvias sin definición con cita")
        t0s = onset_by_agri_year(s.dates, p, region)
        for y, sl in agri_year_slices(s.dates, region).items():
            t0 = t0s.get(y)
            if t0 is None:
                onset_idx[y] = -1
                continue
            seg, m = delay_rain_onset(p[sl], t0 - sl.start, sc.onset_delay_days)
            p[sl] = seg
            dropped += m
            onset_idx[y] = t0 + sc.onset_delay_days
    p = scale_precip(p, sc.precip_factor)
    s2 = replace(s, precip_mm=p)
    s2 = perturb_temperature(s2, base, sc.delta_t_c, sc.humidity)
    cur = derive_climate(s2, base.lat_deg, base.elevation_m, tuple(base.pef_day.keys()), region.phi,
                         region.ea_sensitivity_tol_pct, scenario_id=sc.scenario_id)
    et0_prov = replace(cur.et0_prov, evidence=cap_evidence(cur.et0_prov.evidence, Evidence.C),
                       evidence_rule="scenario.cap_C", assumptions=cur.et0_prov.assumptions + (f"escenario {sc.scenario_id}",))
    pef_prov = {k: replace(v, evidence=cap_evidence(v.evidence, Evidence.C), evidence_rule="scenario.cap_C")
                for k, v in cur.pef_prov.items()}
    base_series = replace(cur.base, precip_prov=replace(cur.base.precip_prov,
                                                        evidence=cap_evidence(cur.base.precip_prov.evidence, Evidence.C),
                                                        evidence_rule="scenario.cap_C"))
    return replace(cur, base=base_series, et0_prov=et0_prov, pef_prov=pef_prov, mass_dropped_mm=dropped,
                   onset_day_idx=onset_idx)


def make_onset_fn(clim: CuratedClimate, region: RegionConfig):
    """Para la lectura onset_rule: t0' sobre la serie (perturbada) del escenario."""
    t0s = onset_by_agri_year(clim.dates, np.asarray(clim.precip_mm), region)

    def fn(agri_year: int):
        t = t0s.get(agri_year)
        return None if t is None else clim.dates[t]

    return fn
