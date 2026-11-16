"""Corrida de R2 de extremo a extremo: serie curada → motor → payloads JSON para R3/R4.

    # con la serie curada de R1
    python tools/r2_run.py --daily data/curated/chiquimula_prueba/daily.parquet --out results/demo
    # sin R1 (serie sintética rotulada)
    python tools/r2_run.py --synthetic --out examples
    # con la grilla de escenarios (45 + lecturas de adaptación)
    python tools/r2_run.py --synthetic --grid --out examples
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "milpa_core" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from milpa_adapter import load_catalogs, load_curated_daily, load_region, load_strategies  # noqa: E402

from milpa_core import BASE, make_context, rank, rank_stability, run_analysis, soil_voi, standard_grid  # noqa: E402
from milpa_core.dto import rank_response_dto, run_summary_dto  # noqa: E402
from milpa_core.enums import AdaptationMode, export_json, export_sql  # noqa: E402
from milpa_core.exposure import dekad_chart  # noqa: E402
from milpa_core.facade import compare_to_base, humidity_sensitivity_flags, run_grid  # noqa: E402
from milpa_core.planting import consistent_windows, heatmap_cycle, heatmap_strategy  # noqa: E402
from milpa_core.report_model import build_report  # noqa: E402
from milpa_core.serialize import to_jsonable  # noqa: E402
from milpa_core.strategy import enumerate_cohorts  # noqa: E402


def dump(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(obj), ensure_ascii=False, indent=2), encoding="utf-8")


def cycle_table(run) -> pd.DataFrame:
    rows = []
    for r in run.cycle_results:
        rows.append({"strategy": r.strategy, "cohort_year": r.cohort_year, "cycle_idx": r.cycle_idx, "variety": r.variety,
                     "anchor_md": r.anchor_md, "plant_date": r.plant_date, "harvest_date": r.harvest_date,
                     "agri_year": r.agri_year, "state": r.state.value, "provisional": r.provisional,
                     "reason": ";".join(r.reasons), "exposure_mm": r.severity_mm,
                     "missing_pct": None if r.evaluability is None else r.evaluability.missing_precip_pct,
                     "state_low": r.state_by_level["low"].value, "state_high": r.state_by_level["high"].value})
    return pd.DataFrame(rows)


def save_table(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path.with_suffix(".parquet"), index=False)
    except Exception:  # sin pyarrow: CSV
        df.to_csv(path.with_suffix(".csv"), index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=str(ROOT / "regions" / "pilot_corredor_seco.yaml"))
    ap.add_argument("--strategies", default=str(ROOT / "regions" / "pilot_corredor_seco.strategies.yaml"))
    ap.add_argument("--catalogs", default=str(ROOT / "catalogs"))
    ap.add_argument("--daily", help="curated/<zona>/daily.parquet de R1 (o CSV)")
    ap.add_argument("--synthetic", action="store_true", help="usar serie sintética rotulada")
    ap.add_argument("--out", default=str(ROOT / "examples"))
    ap.add_argument("--grid", action="store_true", help="ejecutar grilla de 45 escenarios")
    ap.add_argument("--step-days", type=int, default=None)
    a = ap.parse_args(argv)

    t0 = time.time()
    region, extra = load_region(a.region)
    catalogs = load_catalogs(a.catalogs, mode=region.status)
    strategies = load_strategies(a.strategies)
    if a.synthetic:
        from make_synthetic import make
        tmp = Path(a.out) / "_synthetic_daily.csv"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        make(region.window_start, region.window_end).to_csv(tmp, index=False)
        series, info = load_curated_daily(tmp, None, region.window_start, region.window_end)
    else:
        if not a.daily:
            ap.error("--daily o --synthetic")
        series, info = load_curated_daily(a.daily, extra["cell_id"], region.window_start, region.window_end)
    run_id = str(uuid.uuid4())
    ctx = make_context(region, catalogs, series, strategies, crops_enabled=extra["crops_enabled"],
                       ranking_cfg=extra["ranking_cfg"], stability_cfg=extra["stability_cfg"], voi_cfg=extra["voi_cfg"],
                       soil_cfg=extra["soil_cfg"], run_id=run_id)
    out = Path(a.out)
    base = run_analysis(ctx, BASE, AdaptationMode.NONE, a.step_days)
    t_base = time.time() - t0

    # ET0 del motor vs ET0 de R1 (control de paridad)
    et0_check = None
    if info.get("r1_et0_mm") is not None and np.isfinite(info["r1_et0_mm"]).any():
        r1 = info["r1_et0_mm"]
        ok = np.isfinite(r1) & np.isfinite(ctx.base_climate.et0_mm)
        et0_check = {"mean_abs_diff_mm": float(np.mean(np.abs(r1[ok] - ctx.base_climate.et0_mm[ok]))), "n": int(ok.sum())}

    summary = run_summary_dto(base, strategies)
    summary["et0_parity_vs_R1"] = et0_check
    summary["warnings"] = list(ctx.warnings)
    dump(summary, out / "summary.json")
    save_table(cycle_table(base), out / "results" / run_id / "BASE" / "none" / "cycle_result")

    # heatmaps (las dos vistas) + ventanas consistentes
    heat = {}
    for s in strategies:
        sw = s.sweep_cycle()
        if sw is None:
            continue
        hc = heatmap_cycle(list(base.cycle_results), s.code, sw.cycle_idx)
        hs = heatmap_strategy(list(base.strategy_risk), s.code)
        p90 = [next((c.stats["severity_p90_mm"] for c in base.cycle_risk if c.strategy == s.code and c.cycle_idx == sw.cycle_idx
                     and c.anchor_md == d), None) for d in hc["plant_md"]]
        hc["consistent_windows"] = consistent_windows(hc["plant_md"], hc["pct_critical_by_date"], p90)
        heat[s.code] = {"cycle": hc, "strategy": hs}
    dump({"mode": base.decision.mode.value, "label": base.decision.label.value, "scenario": base.tag, "heatmaps": heat},
         out / "heatmap.json")

    # gráfico por decena: primera cohorte, primera fecha, de cada estrategia
    charts = {}
    for s in strategies:
        chs = enumerate_cohorts(s, region, catalogs, series.dates[0], series.dates[-1])
        if chs:
            ci = chs[0].cycles[0]
            if ci.harvest_date is None:
                continue
            charts[s.code] = dekad_chart(ci, base.climate, catalogs, region)
    dump(charts, out / "dekad_chart.json")

    # ranking + estabilidad + VoI
    rk, rk_extra = rank(ctx, base)
    st = rank_stability(rk, ctx.stability_cfg)
    rank_json = rank_response_dto(rk, st, rk_extra)
    rank_json["anchors"] = rk_extra["anchors"]
    dump(rank_json, out / "rank.json")
    voi = soil_voi(ctx, base, rk)
    dump(voi, out / "soil_voi.json")

    # escenarios
    sc_json = None
    if a.grid:
        t1 = time.time()
        ads = [AdaptationMode.NONE] + ([AdaptationMode.ONSET_RULE] if region.onset_rule_enabled else [])
        runs, skipped = run_grid(ctx, standard_grid(), ads, a.step_days)
        comps = []
        for (sid, ad), r in runs.items():
            if sid == "BASE":
                continue
            rr, _ = rank(ctx, r)
            c = compare_to_base(rk, rr, base, r)
            c["adaptation"] = ad
            c["grid_role"] = r.scenario.grid_role
            comps.append(c)
            save_table(cycle_table(r), out / "results" / run_id / sid / ad / "cycle_result")
        hum = humidity_sensitivity_flags(runs, region.communication_tol_pct)
        sc_json = {"n_runs": len(runs), "skipped": {f"{k[0]}|{k[1]}": v for k, v in skipped.items()},
                   "comparisons": comps, "escenario_sensible_a_humedad": hum, "seconds": round(time.time() - t1, 1),
                   "label": "escenario sintético — no es pronóstico"}
        dump(sc_json, out / "scenarios.json")

    report = build_report(summary, rank_json, to_jsonable(voi), (sc_json or {}).get("comparisons"))
    dump(report, out / "report_model.json")
    dump(export_json(), out / "enums.json")
    (out / "enums.sql").write_text(export_sql() + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "mode": base.decision.mode.value, "n_cycle_results": len(base.cycle_results),
                      "ranking_status": rk.status.value, "order": list(rk.order), "stability": st.flag.value,
                      "voi": voi.outcome.value if voi.outcome else voi.applicability.value,
                      "base_seconds": round(t_base, 1), "et0_parity_vs_R1": et0_check, "out": str(out)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
