"""Evaluabilidad de ciclos (apartado 11.2): cada variable por separado, no ``any``."""
from __future__ import annotations

from typing import Any

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Evaluability:
    ok: bool
    missing_precip_pct: float
    missing_met_pct: float
    n_days: int


def pct_missing(a: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    if a.size == 0:
        return 100.0
    return float(100.0 * np.mean(~np.isfinite(a)))


def window_evaluable(precip: Any, met_arrays: list[Any], max_missing_precip_pct: float, max_missing_met_pct: float) -> Evaluability:
    mp = pct_missing(precip)
    mm = max((pct_missing(v) for v in met_arrays), default=0.0)
    ok = mp <= max_missing_precip_pct and mm <= max_missing_met_pct
    return Evaluability(ok, mp, mm, int(np.asarray(precip).size))
