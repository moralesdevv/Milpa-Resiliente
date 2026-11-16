"""Recalibra los umbrales SANDBOX de catalogs/r2/thresholds.yaml con la serie curada real.

NO produce umbrales agronómicos: elige el umbral para que el criterio de agua discrimine en la
demostración. Para cada ciclo calcula la exposición "de quiebre" (máximo por decena crítica de
e · días_decena / días_en_etapa: el ciclo es crítico si y solo si supera el umbral) y fija
  sens_low = P{low}, value = P{central}, sens_high = P{high}   (por cultivo)
Con central = P65 ≈ 35 % de los ciclos quedan críticos en la línea base. Los umbrales siguen
sin cita → todo sigue rotulado «umbral provisional — no usar para decisión».

    python tools/calibrate_sandbox_thresholds.py --daily data/curated/chiquimula_prueba/daily.parquet
"""
from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "milpa_core" / "src"))
sys.path.insert(0, str(ROOT / "tools" / "r2"))

from milpa_adapter import load_catalogs, load_curated_daily, load_region, load_strategies  # noqa: E402

from milpa_core import BASE, make_context, rank, run_analysis  # noqa: E402


def breakpoints(run, min_seg: int = 1) -> dict[str, list[float]]:
    out = defaultdict(list)
    for r in run.cycle_results:
        for c in r.components:
            if c.segments:
                segs = [g for g in c.segments if g.n_days >= min_seg]
                if segs:
                    out[c.crop].append(max(g.exposure_mm * g.dekad_days / g.n_days for g in segs))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", required=True)
    ap.add_argument("--region", default=str(ROOT / "regions" / "r2" / "pilot_corredor_seco.yaml"))
    ap.add_argument("--strategies", default=str(ROOT / "regions" / "r2" / "pilot_corredor_seco.strategies.yaml"))
    ap.add_argument("--catalogs", default=str(ROOT / "catalogs" / "r2"))
    ap.add_argument("--low", type=float, default=50)
    ap.add_argument("--central", type=float, default=65)
    ap.add_argument("--high", type=float, default=80)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    region, extra = load_region(a.region)
    cat_dir = Path(a.catalogs)
    catalogs = load_catalogs(cat_dir, mode=region.status)
    strategies = load_strategies(a.strategies)
    series, _ = load_curated_daily(a.daily, extra["cell_id"], region.window_start, region.window_end)
    ctx = make_context(region, catalogs, series, strategies, crops_enabled=extra["crops_enabled"],
                       ranking_cfg=extra["ranking_cfg"], soil_cfg=extra["soil_cfg"])
    bp = breakpoints(run_analysis(ctx, BASE), region.min_segment_days)

    path = cat_dir / "thresholds.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    print(f"{'cultivo':8} {'n':>4}  {'P10':>6} {'P50':>6} {'P90':>6}   →  low / central / high (mm por decena)")
    for t in doc["thresholds"]:
        v = np.asarray(bp.get(t["crop"], []), dtype=float)
        if v.size < 5:
            print(f"{t['crop']:8} {v.size:>4}  sin suficientes ciclos; se deja igual")
            continue
        lo, ce, hi = (round(float(np.percentile(v, q)), 1) for q in (a.low, a.central, a.high))
        print(f"{t['crop']:8} {v.size:>4}  {np.percentile(v, 10):6.1f} {np.percentile(v, 50):6.1f} {np.percentile(v, 90):6.1f}"
              f"   →  {lo} / {ce} / {hi}")
        t.update({"value": ce, "sens_low": lo, "sens_high": hi, "citation": None, "evidence": "C"})
    if a.dry_run:
        return
    shutil.copy(path, path.with_suffix(".yaml.bak"))
    header = ("# Umbrales de exposición — SANDBOX recalibrados con la serie curada real\n"
              f"# (percentiles {a.low:g}/{a.central:g}/{a.high:g} de la exposición de quiebre por ciclo en la línea base).\n"
              "# NO son umbrales agronómicos ni tienen cita: solo hacen que la demostración discrimine.\n"
              "# Reemplazar por umbrales con cita (DE-08). Copia anterior: thresholds.yaml.bak\n")
    path.write_text(header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"\nescrito {path} (respaldo .bak)")

    # verificación rápida con los nuevos umbrales
    ctx2 = make_context(region, load_catalogs(cat_dir, mode=region.status), series, strategies,
                        crops_enabled=extra["crops_enabled"], ranking_cfg=extra["ranking_cfg"], soil_cfg=extra["soil_cfg"])
    run2 = run_analysis(ctx2, BASE)
    r, x = rank(ctx2, run2)
    print("\nranking con umbrales recalibrados:")
    for s in r.order:
        w = x["criteria"][s]
        print(f"  {s:26} total={r.totals[s]:.3f}  agua={w[list(w)[0]].value:.2f}  suelo={w[list(w)[1]].value:.3f}"
              f"  ancla={x['anchors'][s]}")
    nd = [d["criterion"] for d in r.decision_log if d["decision"] == "criterio_no_discriminante"]
    print("criterios no discriminantes:", nd or "ninguno")


if __name__ == "__main__":
    main()
