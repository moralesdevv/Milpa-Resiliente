"""ET0 FAO-56 Penman–Monteith diaria y presión real de vapor (apartado 11.3).

Todas las funciones son vectorizadas (numpy) y puras. Unidades: T °C, u2 m/s,
Rs/Rn MJ m-2 d-1, presiones kPa, ET0 mm/d. G = 0 en paso diario.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from ..enums import EaMethod

SIGMA = 4.903e-9  # MJ K-4 m-2 d-1
GSC = 0.0820  # MJ m-2 min-1


def sat_vp(t_c: Any) -> np.ndarray:
    """e°(T) en kPa (FAO-56 ec. 11)."""
    t = np.asarray(t_c, dtype=float)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def es_from(tmax_c: Any, tmin_c: Any) -> np.ndarray:
    return np.asarray((sat_vp(tmax_c) + sat_vp(tmin_c)) / 2.0)


def slope_vp(t_c: Any) -> np.ndarray:
    """Δ en kPa/°C (ec. 13) con T media."""
    t = np.asarray(t_c, dtype=float)
    return 4098.0 * sat_vp(t) / (t + 237.3) ** 2


def pressure_kpa(z_m: Any) -> np.ndarray:
    """P con la elevación del DEM, no la de la rejilla de POWER (ec. 7)."""
    return 101.3 * ((293.0 - 0.0065 * np.asarray(z_m, dtype=float)) / 293.0) ** 5.26


def psychro(z_m: Any) -> np.ndarray:
    """γ = 0.665e-3 · P (ec. 8)."""
    return 0.665e-3 * pressure_kpa(z_m)


def extraterrestrial_radiation(lat_deg: Any, doy: Any) -> np.ndarray:
    """Ra en MJ m-2 d-1 (ec. 21-25)."""
    phi = np.deg2rad(np.asarray(lat_deg, dtype=float))
    j = np.asarray(doy, dtype=float)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    delta = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0))
    return np.asarray(
        (24 * 60 / np.pi) * GSC * dr * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    )


def clear_sky_radiation(ra: Any, z_m: Any) -> np.ndarray:
    return np.asarray((0.75 + 2e-5 * np.asarray(z_m, dtype=float)) * ra)


def net_longwave(tmax_c: Any, tmin_c: Any, ea_kpa: Any, rs: Any, rso: Any) -> np.ndarray:
    """Rnl (ec. 39) con Rs/Rso acotado a 1."""
    ratio = np.clip(np.divide(rs, rso, out=np.ones_like(np.asarray(rs, dtype=float)), where=np.asarray(rso) > 0), 0.0, 1.0)
    tk4 = ((np.asarray(tmax_c) + 273.16) ** 4 + (np.asarray(tmin_c) + 273.16) ** 4) / 2
    return np.asarray(SIGMA * tk4 * (0.34 - 0.14 * np.sqrt(np.maximum(ea_kpa, 0.0))) * (1.35 * ratio - 0.35))


def hargreaves_rs(tmax_c: Any, tmin_c: Any, ra: Any, krs: float = 0.16) -> np.ndarray:
    """Rs por Hargreaves–Samani (ec. 50) — solo si falta Rs; evidencia C."""
    return np.asarray(krs * np.sqrt(np.maximum(np.asarray(tmax_c) - np.asarray(tmin_c), 0.0)) * ra)


def wind_to_2m(u_z: Any, z_m: Any) -> np.ndarray:
    """Perfil logarítmico FAO-56 (ec. 47)."""
    return np.asarray(u_z) * 4.87 / np.log(67.8 * z_m - 5.42)


def actual_vp(tmax_c: Any, tmin_c: Any, tdew_c: Any = None, rh_pct: Any = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ea por dos rutas, día a día (apartado 11.3).

    Ruta R1 (preferente): ea = e°(Tdew) si T2MDEW existe y pasa QC (Tdew ≤ Tmax).
    Ruta R2 (alternativa): ea = RH2M/100 · es (FAO-56, caso de solo RHmean).
    Devuelve (ea_kpa, method[str array], capped[bool array]) con ea ≤ es.
    """
    tmax = np.asarray(tmax_c, dtype=float)
    tmin = np.asarray(tmin_c, dtype=float)
    n = tmax.shape[0]
    es = es_from(tmax, tmin)
    ea = np.full(n, np.nan)
    method = np.full(n, EaMethod.MISSING.value, dtype=object)
    if tdew_c is not None:
        td = np.asarray(tdew_c, dtype=float)
        ok = np.isfinite(td) & (td <= tmax + 0.5) & (td > -60)
        ea[ok] = sat_vp(td[ok])
        method[ok] = EaMethod.DEWPOINT.value
    if rh_pct is not None:
        rh = np.asarray(rh_pct, dtype=float)
        need = ~np.isfinite(ea) & np.isfinite(rh) & (rh >= 0) & (rh <= 100)
        ea[need] = rh[need] / 100.0 * es[need]
        method[need] = EaMethod.RH_MEAN.value
    capped = np.isfinite(ea) & (ea > es)
    ea = np.where(capped, es, ea)
    return ea, method, capped


def et0_fao56(tmax_c: Any, tmin_c: Any, rs_mj_m2: Any, u2_ms: Any, ea_kpa: Any, z_m: Any, lat_deg: Any, doy: Any) -> tuple[np.ndarray, np.ndarray]:
    """ET0 diaria FAO-56 PM (ec. 6). Devuelve (et0_mm, raw_negative[bool])."""
    tmax = np.asarray(tmax_c, dtype=float)
    tmin = np.asarray(tmin_c, dtype=float)
    t = (tmax + tmin) / 2.0
    es = es_from(tmax, tmin)
    ea = np.asarray(ea_kpa, dtype=float)
    d = slope_vp(t)
    g = psychro(z_m)
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = clear_sky_radiation(ra, z_m)
    rs = np.asarray(rs_mj_m2, dtype=float)
    rn = 0.77 * rs - net_longwave(tmax, tmin, ea, rs, rso)
    u2 = np.asarray(u2_ms, dtype=float)
    num = 0.408 * d * rn + g * (900.0 / (t + 273.0)) * u2 * (es - ea)
    den = d + g * (1 + 0.34 * u2)
    raw = num / den
    neg = np.isfinite(raw) & (raw < 0)
    return np.where(neg, 0.0, raw), neg
