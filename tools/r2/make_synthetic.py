"""Serie diaria SINTÉTICA rotulada con forma de curated/daily.parquet (para correr R2 sin R1).

Régimen bimodal tipo Corredor Seco: primera (mayo–jun), canícula (jul–ago), postrera (sep–oct),
seca (nov–abr). Los valores son inventados para pruebas: NO son datos de la zona.

    python tools/make_synthetic.py --out data/demo/synthetic_daily.csv
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


def make(start="2021-01-01", end="2025-12-31", seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    d = pd.date_range(start, end, freq="D")
    doy = d.dayofyear.to_numpy()
    yrs = d.year.to_numpy()
    # intensidad de canícula distinta por año (para que el ranking tenga algo que ver)
    can = {y: rng.uniform(0.15, 0.9) for y in np.unique(yrs)}
    wet = np.zeros(len(d))
    wet += 0.55 * np.exp(-0.5 * ((doy - 160) / 18) ** 2)  # primera
    wet += 0.60 * np.exp(-0.5 * ((doy - 265) / 22) ** 2)  # postrera
    wet += np.array([0.25 * (1 - can[y]) for y in yrs]) * np.exp(-0.5 * ((doy - 210) / 15) ** 2)  # canícula
    wet = np.clip(wet + 0.03, 0, 0.9)
    rainy = rng.uniform(size=len(d)) < wet
    p = np.where(rainy, rng.gamma(0.9, 12.0, size=len(d)), 0.0)
    tmax = 31 + 3 * np.sin(2 * np.pi * (doy - 100) / 365) - 2.5 * wet + rng.normal(0, 1.0, len(d))
    tmin = 18 + 2 * np.sin(2 * np.pi * (doy - 120) / 365) + 1.5 * wet + rng.normal(0, 0.8, len(d))
    tdew = tmin - 1.5 + 4 * wet + rng.normal(0, 0.8, len(d))
    rh = np.clip(55 + 35 * wet + rng.normal(0, 5, len(d)), 15, 99)
    wind = np.clip(2.2 - 0.8 * wet + rng.normal(0, 0.3, len(d)), 0.3, None)
    srad = np.clip(22 - 7 * wet + rng.normal(0, 1.5, len(d)), 5, 30)
    df = pd.DataFrame({
        "cell_id": "synthetic_0", "obs_date": d.date, "tmax_c": tmax, "tmin_c": tmin, "tmean_c": (tmax + tmin) / 2,
        "tdew_c": tdew, "rh_pct": rh, "wind2m_ms": wind, "srad_mj_m2": srad, "precip_mm": p,
        "precip_source": "SYNTHETIC", "ea_method": None, "et0_mm": np.nan, "qc_flags": 0,
    })
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo/synthetic_daily.csv")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    df = make(seed=a.seed)
    if a.out.endswith(".parquet"):
        df.to_parquet(a.out, index=False)
    else:
        df.to_csv(a.out, index=False)
    print(f"escrito {a.out}: {len(df)} días (SINTÉTICO)")
