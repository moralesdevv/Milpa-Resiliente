"""Decenas: 1–10, 11–20, 21–fin de mes → 36 por año (índice 1..36)."""
from __future__ import annotations

import numpy as np


def ymd(dates: np.ndarray):
    d = np.asarray(dates, dtype="datetime64[D]")
    y = d.astype("datetime64[Y]").astype(int) + 1970
    m = d.astype("datetime64[M]").astype(int) % 12 + 1
    day = (d - d.astype("datetime64[M]")).astype(int) + 1
    return y, m, day


def doy(dates: np.ndarray) -> np.ndarray:
    d = np.asarray(dates, dtype="datetime64[D]")
    return (d - d.astype("datetime64[Y]")).astype(int) + 1


def dekad_of(dates: np.ndarray):
    """Devuelve (year, dekad_idx 1..36, key entero año*100+dekad)."""
    y, m, day = ymd(dates)
    k = np.where(day <= 10, 1, np.where(day <= 20, 2, 3))
    idx = (m - 1) * 3 + k
    return y, idx, y * 100 + idx


def dekad_length(year: int, dekad_idx: int) -> int:
    m = (dekad_idx - 1) // 3 + 1
    k = (dekad_idx - 1) % 3 + 1
    if k < 3:
        return 10
    start = np.datetime64(f"{year:04d}-{m:02d}-21")
    nxt = np.datetime64(f"{year + (m == 12):04d}-{(m % 12) + 1:02d}-01")
    return int((nxt - start).astype(int))


def month_key(dates: np.ndarray) -> np.ndarray:
    y, m, _ = ymd(dates)
    return y * 100 + m
