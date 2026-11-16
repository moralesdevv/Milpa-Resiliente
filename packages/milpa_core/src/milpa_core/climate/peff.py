"""Precipitación efectiva por decena (apartado 11.4).

Cada método se aplica en su escala nativa (mes o sin escala) y se desagrega a
decenas y a días por proporción de P. La desagregación es una asignación, no un
proceso físico. Si un mes tiene algún día de P faltante (o está incompleto en la
serie), los métodos mensuales devuelven NaN para ese mes y sus decenas/días.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from ..enums import MONTHLY_PEFF, PeffMethod
from .dekad import month_key, ymd


def usda_scs_fao_month(p_month: Any) -> np.ndarray:
    """Pef = P·(125−0.2P)/125 si P ≤ 250; 125 + 0.1P si P > 250  [Verificar]."""
    p = np.asarray(p_month, dtype=float)
    return np.where(p <= 250.0, p * (125.0 - 0.2 * p) / 125.0, 125.0 + 0.1 * p)


def fao_dependable_month(p_month: Any) -> np.ndarray:
    """Pef = 0.6P−10 si P ≤ 70; 0.8P−24 si P > 70; mínimo 0  [Verificar]."""
    p = np.asarray(p_month, dtype=float)
    return np.maximum(0.0, np.where(p <= 70.0, 0.6 * p - 10.0, 0.8 * p - 24.0))


MONTHLY_FORMULA: dict[PeffMethod, Callable[[Any], np.ndarray]] = {
    PeffMethod.USDA_SCS_FAO: usda_scs_fao_month,
    PeffMethod.FAO_DEPENDABLE: fao_dependable_month,
}


def pef_daily(dates: np.ndarray, p_mm: np.ndarray, method: PeffMethod, phi: float | None = None) -> np.ndarray:
    """Pef asignada a cada día. Suma por decena = Pef de la decena; por mes = Pef mensual."""
    p = np.asarray(p_mm, dtype=float)
    method = PeffMethod(method)
    if method is PeffMethod.UPPER_BOUND:
        return p.copy()
    if method is PeffMethod.FIXED_FRACTION:
        if phi is None or not (0.0 <= phi <= 1.0):
            raise ValueError("fixed_fraction requiere phi en [0,1] del region pack")
        return phi * p
    if method not in MONTHLY_PEFF:
        raise ValueError(f"método de Pef desconocido: {method}")
    mk = month_key(dates)
    y, m, day = ymd(dates)
    out = np.full(p.shape, np.nan)
    for key in np.unique(mk):
        sel = mk == key
        yy, mm = divmod(int(key), 100)
        n_days_month = int((np.datetime64(f"{yy + (mm == 12):04d}-{mm % 12 + 1:02d}-01")
                            - np.datetime64(f"{yy:04d}-{mm:02d}-01")).astype(int))
        pm = p[sel]
        if sel.sum() != n_days_month or not np.all(np.isfinite(pm)):
            continue  # NaN: mes incompleto o con faltantes (nunca relleno de lluvia)
        tot = pm.sum()
        if tot <= 0:
            out[sel] = 0.0
            continue
        pef_m = float(MONTHLY_FORMULA[method](tot))
        out[sel] = pm * (pef_m / tot)
    return out


def pef_monthly(dates: np.ndarray, p_mm: np.ndarray, method: PeffMethod, phi: float | None = None) -> Any:
    """(month_keys, P_mes, Pef_mes) para pruebas e informe."""
    d = pef_daily(dates, p_mm, method, phi)
    mk = month_key(dates)
    keys = np.unique(mk)
    pm = np.array([np.sum(np.asarray(p_mm)[mk == k]) for k in keys])
    em = np.array([np.sum(d[mk == k]) if np.all(np.isfinite(d[mk == k])) else np.nan for k in keys])
    return keys, pm, em
