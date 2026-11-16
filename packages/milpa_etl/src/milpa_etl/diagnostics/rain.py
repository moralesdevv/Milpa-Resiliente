#!/usr/bin/env python3
"""
diagnostico_lluvia.py — ¿por qué IMERG y POWER discrepan? Separa causas posibles.

    Lee (sin modificar nada):
    data/curated/<zona>/daily.(parquet|csv)        -> lluvia de POWER
    data/clean/imerg/<zona>/*.(parquet|csv)         -> serie zonal de IMERG (la que escribe fetch-imerg)

    Qué mira y qué indicaría:
    1. Desfase en días  : si la correlación diaria máxima NO está en 0, hay un desajuste de día (UTC vs local u otro).
    2. Estacionalidad   : si ambos productos no tienen ciclo húmedo/seco parecido, uno de los dos es sospechoso.
    3. Anomalías        : correlación mensual SIN el ciclo estacional (lo que queda es variabilidad entre años).
    4. Eventos extremos : si los días más lluviosos de uno coinciden (±1 día) con los del otro.
    5. Distribución     : frecuencia de días con lluvia y percentiles; un producto "llovizna" o un producto "explota".
    Ninguno de los dos es la verdad: con esto se descartan errores de código, no se decide cuál acierta
    (eso requiere una estación en la zona).

Uso:  python diagnostico_lluvia.py --zone chiquimula_prueba
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def read_base(base: Path) -> pd.DataFrame:
    for ext, fn in ((".parquet", pd.read_parquet), (".csv", lambda p: pd.read_csv(p, index_col=0))):
        p = base.with_suffix(ext)
        if p.exists():
            return fn(p)
    raise FileNotFoundError(f"no existe {base}.parquet ni {base}.csv")


def load_imerg(d: Path) -> pd.Series:
    files = sorted(d.glob("*.parquet")) or sorted(d.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no hay archivos de IMERG en {d}")
    parts = []
    for f in files:
        df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f, index_col=0)
        df.index = pd.to_datetime(df.index)
        parts.append(df["precip_mm"])
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")]


def complete_months(s: pd.Series, other: pd.Series) -> pd.DataFrame:
    both = pd.concat([s, other], axis=1, keys=["imerg", "power"])
    both = both.where(both.notna().all(axis=1))
    g = both.groupby([both.index.year, both.index.month])
    tot, n = g.sum(min_count=1), g.count()["imerg"]
    size = pd.Series([pd.Period(f"{y}-{m:02d}").days_in_month for y, m in tot.index], index=tot.index)
    tot = tot[n == size]
    tot.index = pd.MultiIndex.from_tuples(tot.index, names=["año", "mes"])
    return tot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--data-dir", default="data")
    a = ap.parse_args()
    dd = Path(a.data_dir)
    try:
        daily = read_base(dd / "curated" / a.zone / "daily")
        imerg = load_imerg(dd / "clean" / "imerg" / a.zone)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    daily.index = pd.to_datetime(daily.index)
    power = daily["precip_power_mm"] if "precip_power_mm" in daily.columns else daily["precip_mm"]
    common = imerg.notna() & power.reindex(imerg.index).notna()
    print(f"IMERG: {imerg.index.min().date()} a {imerg.index.max().date()} "
            f"({imerg.notna().sum()} días con dato) | días en común con POWER: {int(common.sum())}")
    if imerg.index.has_duplicates or not imerg.index.is_monotonic_increasing:
        print("AVISO: la serie de IMERG tiene fechas duplicadas o desordenadas")
    idx = imerg.index[common]
    im, po = imerg.loc[idx], power.loc[idx]
    if len(idx) < 60:
        print("Muy pocos días en común para diagnosticar.")
        return 1

    print("\n== 1. Correlación diaria con IMERG desplazado k días (k=0 es sin desplazar) ==")
    rows = []
    for k in range(-3, 4):
        sh = imerg.shift(k)                      # k>0: el valor de IMERG de ayer se compara con POWER de hoy
        j = pd.concat([sh, power], axis=1, keys=["i", "p"]).dropna()
        rows.append((k, round(float(j.corr().iloc[0, 1]), 3), len(j)))
    lag = pd.DataFrame(rows, columns=["k_dias", "corr", "n"])
    print(lag.to_string(index=False))
    best = lag.loc[lag["corr"].idxmax()]
    print(f"-> máximo en k={int(best.k_dias)} (corr {best['corr']}). "
            + ("Sin desfase de día claro." if int(best.k_dias) == 0 else "HAY un desfase de día: revisar la convención de día."))

    m = complete_months(imerg, power)
    print(f"\n== 2. Totales mensuales ({len(m)} meses completos en común) ==")
    if len(m) >= 12:
        clim = m.groupby(level="mes").mean().round(0)
        clim["ratio"] = (clim["imerg"] / clim["power"]).round(2)
        print("Clima mensual medio (mm/mes):")
        print(clim.to_string())
        print(f"corr mensual total: {m.corr().iloc[0, 1]:.3f}")
        anom = m - m.groupby(level="mes").transform("mean")
        print(f"corr mensual de ANOMALÍAS (sin ciclo estacional): {anom.corr().iloc[0, 1]:.3f}")
        print("   (si la total es baja y la de anomalías también, los productos no comparten ni el ciclo estacional)")
    else:
        print("menos de 12 meses completos: faltan datos para comparar el ciclo estacional")

    print("\n== 3. Dekadas (la unidad de cálculo del proyecto) ==")
    both = pd.concat([im, po], axis=1, keys=["i", "p"])
    dk = both.groupby([both.index.year, both.index.month, np.minimum((both.index.day - 1) // 10, 2)])
    s, n = dk.sum(), dk.count()["i"]
    s = s[n >= 9]
    print(f"{len(s)} dekadas casi completas; corr dekadal: {s.corr().iloc[0, 1]:.3f}")

    print("\n== 4. Días más lluviosos de IMERG y POWER (¿coinciden en fecha?) ==")
    top = im.nlargest(8)
    out = []
    for d, v in top.items():
        win = po.loc[d - pd.Timedelta(days=1): d + pd.Timedelta(days=1)]
        out.append((d.date(), round(v, 1), round(float(po.get(d, np.nan)), 1), round(float(win.max()), 1)))
    print(pd.DataFrame(out, columns=["fecha", "IMERG", "POWER_mismo_dia", "POWER_max_±1d"]).to_string(index=False))
    top2 = po.nlargest(8)
    out = []
    for d, v in top2.items():
        win = im.loc[d - pd.Timedelta(days=1): d + pd.Timedelta(days=1)]
        out.append((d.date(), round(v, 1), round(float(im.get(d, np.nan)), 1), round(float(win.max()), 1)))
    print(pd.DataFrame(out, columns=["fecha", "POWER", "IMERG_mismo_dia", "IMERG_max_±1d"]).to_string(index=False))

    print("\n== 5. Distribución diaria ==")
    q = pd.DataFrame({"IMERG": im.describe(percentiles=[.5, .9, .99]), "POWER": po.describe(percentiles=[.5, .9, .99])}).round(2)
    print(q.to_string())
    print(f"frecuencia de días con >= 1 mm: IMERG {(im >= 1).mean():.2f} | POWER {(po >= 1).mean():.2f}")
    print(f"frecuencia de días secos (0 mm): IMERG {(im == 0).mean():.2f} | POWER {(po == 0).mean():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
