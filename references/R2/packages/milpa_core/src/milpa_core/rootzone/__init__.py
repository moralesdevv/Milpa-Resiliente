"""Modo B — balance hídrico de la zona radicular (apartado 11.8). Solo si gating lo autoriza.

Usa P diaria que llega al suelo (no Pef). Supuestos: RO = 0 salvo parámetro citado,
sin ascenso capilar, Kc único; al profundizar la raíz se conserva la lámina de
agotamiento absoluta (agua nueva a capacidad de campo).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..climate.series import CuratedClimate
from ..config import RegionConfig
from ..crops import Catalogs, Threshold
from ..enums import CellState, Evidence, Mode, Reason
from ..exposure import LEVELS, CycleResult, _not_evaluable, cycle_evaluability
from ..provenance import min_evidence
from ..soil import SoilContext
from ..strategy import CycleInstance


@dataclass(frozen=True)
class BucketResult:
    dr_mm: np.ndarray
    ks: np.ndarray
    dp_mm: np.ndarray
    taw_mm: np.ndarray
    raw_mm: np.ndarray
    eta_mm: np.ndarray


def simulate_bucket(p_mm, et0_mm, kc, zr_m, awc_mm_m: float, z_soil_m: float, p_frac: float, dr0_mm: float,
                    ro_mm=None) -> BucketResult:
    p = np.asarray(p_mm, dtype=float)
    n = p.size
    ro = np.zeros(n) if ro_mm is None else np.asarray(ro_mm, dtype=float)
    zr = np.minimum(np.asarray(zr_m, dtype=float), z_soil_m)
    taw = awc_mm_m * zr
    raw = p_frac * taw
    dr = np.zeros(n)
    ks = np.ones(n)
    dp = np.zeros(n)
    eta = np.zeros(n)
    prev = float(np.clip(dr0_mm, 0, taw[0] if n else 0))
    for t in range(n):
        if prev <= raw[t]:
            k = 1.0
        else:
            k = max(0.0, (taw[t] - prev) / ((1 - p_frac) * taw[t])) if taw[t] > 0 else 0.0
        et = k * kc[t] * et0_mm[t]
        infil = p[t] - ro[t]
        d_t = max(0.0, infil - et - prev)  # percolación profunda
        cur = prev - infil + et + d_t
        cur = min(max(cur, 0.0), taw[t])
        dr[t], ks[t], dp[t], eta[t] = cur, k, d_t, et
        prev = cur
    return BucketResult(dr, ks, dp, taw, raw, eta)


def root_depth_series(cal, z_min: float, z_max: float) -> np.ndarray:
    """Zr crece linealmente de z_min a z_max hasta el fin de la etapa de desarrollo (2.ª etapa)."""
    n = cal.n_days
    if len(cal.stage_codes) >= 2:
        end_dev = int(np.nonzero(cal.stage_idx <= 1)[0][-1]) + 1
    else:
        end_dev = n
    z = np.full(n, z_max)
    z[:end_dev] = z_min + (z_max - z_min) * np.arange(end_dev) / max(end_dev - 1, 1)
    return z


def evaluate_cycle_rootzone(ci: CycleInstance, clim: CuratedClimate, catalogs: Catalogs, region: RegionConfig,
                            soil: SoilContext, dr0_override: float | None = None) -> CycleResult:
    method = "daily_precip_to_soil"
    if ci.invalid_reason or ci.plant_date is None or ci.harvest_date is None:
        return _not_evaluable(ci, Mode.ROOT_ZONE, method, ci.invalid_reason or "fechas_no_calculables")
    if not clim.covers(ci.plant_date, ci.harvest_date):
        return _not_evaluable(ci, Mode.ROOT_ZONE, method, "fuera_de_la_ventana_de_datos")
    ev = cycle_evaluability(ci, clim, region)
    if not ev.ok:
        return _not_evaluable(ci, Mode.ROOT_ZONE, method, "cobertura_insuficiente", ev)
    awc = soil.property("awc_mm_m").value
    zsoil = soil.property("effective_depth").value
    dr0 = soil.initial_condition.dr0_mm if dr0_override is None else dr0_override
    comp = ci.components[0]
    v, cal = comp.variety, comp.calendar
    sl = clim.sl(cal.plant_date, cal.harvest_date)
    zr = root_depth_series(cal, v.z_min_m, v.z_max_m)
    b = simulate_bucket(np.nan_to_num(clim.precip_mm[sl]), clim.et0_mm[sl], cal.kc, zr, awc, zsoil,
                        v.depletion_fraction_p, dr0)
    crit = cal.critical
    stress = float(np.sum((1 - b.ks)[crit]))
    thr: Threshold | None = catalogs.threshold(v.crop, next((s.code for s in v.critical_stages), ""), None, Mode.ROOT_ZONE)
    reasons, provisional = [], False
    state = {}
    for lv in LEVELS:
        if thr is None:
            state[lv] = CellState.INSUFFICIENT_DATA
        else:
            val = thr.at(lv) if thr.at(lv) is not None else thr.value
            state[lv] = CellState.CRITICAL if stress > val else CellState.NON_CRITICAL
    if thr is None:
        reasons.append(Reason.PROVISIONAL_SIN_CITA.value)
    elif not thr.cited:
        provisional = True
        reasons.append(Reason.UMBRAL_SANDBOX.value)
    if not v.fallow_kc_citation:
        reasons.append(Reason.SIN_CONTINUIDAD_DE_SUELO.value)
    soil_ev = [soil.property("awc_mm_m").evidence, soil.property("effective_depth").evidence]
    evid = min_evidence([clim.base.precip_prov.evidence, clim.et0_prov.evidence, v.kc_evidence,
                         thr.evidence if (thr and thr.cited) else Evidence.C] + soil_ev)
    return CycleResult(ci.strategy, ci.cohort_year, ci.cycle_idx, ci.anchor_md, ci.season, ci.agri_year, ci.calendar_year,
                       ci.principal_variety, str(ci.plant_date), str(ci.harvest_date), Mode.ROOT_ZONE, method,
                       state["central"], state, stress, provisional, tuple(reasons), ev, (), evid, {}, stress_days=stress,
                       adapted=ci.adapted)
