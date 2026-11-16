#!/usr/bin/env python3
"""
    registrar_procedencia.py — DE-07: escribe en prov.indicator_provenance la
    procedencia y la evidencia A/B/C de los indicadores curados de una zona.

    Lee: data/curated/<zona>/{curated_meta.json, daily, coverage, validation_report.json}
        catalogs/evidence_rules.yaml
    Escribe (si no se usa --dry-run): prov.indicator_provenance.

    Requisitos: haber ejecutado antes milpa_r1.py curate y cargar_manifiesto.py.
    Dependencias: pandas, pyyaml, psycopg[binary] (psycopg solo sin --dry-run).

    Uso:
    python registrar_procedencia.py --zone chiquimula_prueba --dry-run
    python registrar_procedencia.py --zone chiquimula_prueba
    Variable de entorno requerida (o archivo .env): DATABASE_URL
"""
import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

ORDER = {"A": 3, "B": 2, "C": 1}


def min_evidence(*levels: str) -> str:
    """La evidencia es el MÍNIMO de las de sus insumos, nunca el máximo."""
    return min(levels, key=lambda lv: ORDER[lv])


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_table(base: Path) -> pd.DataFrame:
    pq = base.with_suffix(".parquet")
    if pq.exists():
        return pd.read_parquet(pq)
    df = pd.read_csv(base.with_suffix(".csv"), index_col=0)
    if df.index.name == "obs_date":
        df.index = pd.to_datetime(df.index)
    return df


def build_rows(zone: str, data_dir: Path, rules: dict) -> list[dict]:
    zdir = data_dir / "curated" / zone
    meta = json.loads((zdir / "curated_meta.json").read_text(encoding="utf-8"))
    daily = read_table(zdir / "daily")
    daily.index = pd.to_datetime(daily.index)
    cov = read_table(zdir / "coverage")
    vr_path = zdir / "validation_report.json"
    vr = json.loads(vr_path.read_text(encoding="utf-8")) if vr_path.exists() else None

    r = rules["rules"]
    period = (daily.index.min().date(), daily.index.max().date())
    pv_path = zdir / "precip_validation.json"
    pv = json.loads(pv_path.read_text(encoding="utf-8")) if pv_path.exists() else {}
    all_hashes = meta["raw_sha256"]
    power_hashes = meta.get("raw_sha256_power") or all_hashes

    # --- lluvia (POWER primaria: regla provisional) ---
    cp = cov[cov.variable == "precip_mm"]
    precip_missing = round(100 * (1 - cp.n_valid.sum() / cp.n_expected.sum()), 3)
    if meta.get("precip_primary") == "IMERG_FINAL_V07":
        has_station = "IMERG_vs_station" in pv and "corr_daily" in pv["IMERG_vs_station"]
        rule_p = "precip_imerg_b" if has_station else "precip_imerg_c_no_validation"
        fb = meta.get("fallback_share_pct", 0.0)
        precip_row = {
            "indicator_code": "precip_mm", "unit": "mm/día",
            "provenance": r[rule_p]["provenance"], "evidence": r[rule_p]["evidence"], "rule": rule_p,
            "method": "IMERG Final V07 (media ponderada por área de las celdas de 0.1° de la zona); "
                        "POWER PRECTOTCORR como respaldo (bit 32); sin interpolación de lluvia",
            "missing_pct": precip_missing,
            "assumptions": [f"{meta.get('imerg_n_cells', '?')} celdas de 0.1°; día válido si las celdas con dato "
                            f"suman al menos {meta.get('min_weight_cov')} del peso de la zona [Pendiente]"],
            "limitations": [
                f"días de respaldo POWER: {fb}% (fallback_share_max pendiente, DP-08)",
                "sin validación en la zona (estación): evidencia C" if not has_station
                else "validada contra estación; tope B sin verificación local ampliada",
                "resolución ~0.1°; no es un valor de parcela",
                "convención de día UTC frente a UTC-6 [Verificar]",
            ],
        }
        ev_precip = precip_row["evidence"]
        precip_hashes = all_hashes
        if meta.get("imerg_window"):
            precip_row["assumptions"].append(
                f"ventana de IMERG: {meta['imerg_window'][0]} a {meta['imerg_window'][1]} "
                f"({meta.get('imerg_window_days')} días); fuera de ella la lluvia es solo POWER")
            precip_row["limitations"].append(
                f"POWER trae {meta.get('power_spike_days', 0)} días atípicos (>=100 mm con IMERG <10 mm)")
    else:
        rule_p = "precip_power_provisional"
        ev_precip = r[rule_p]["evidence"]
        precip_row = {
            "indicator_code": "precip_mm", "unit": "mm/día",
            "provenance": r[rule_p]["provenance"], "evidence": ev_precip, "rule": rule_p,
            "method": "POWER PRECTOTCORR sin transformación; sin interpolación de lluvia",
            "missing_pct": precip_missing,
            "assumptions": ["POWER PRECTOTCORR usada como serie primaria (IMERG no incorporado)"],
            "limitations": [
                "regla de evidencia propuesta, pendiente de decisión con R2",
                "resolución de celda ~0.5°x0.625° [Verificar]; no es un valor de parcela",
                "convención de día de POWER frente a UTC-6 [Verificar]",
                "evidencia máxima B sin verificación local",
            ],
        }
        precip_hashes = power_hashes

    # --- ET0 ---
    rad_modeled_days = int(((daily.qc_flags.astype(int) & 16) > 0).sum())
    rule_e = "et0_c_rad_modeled" if rad_modeled_days > 0 else "et0_b_dewpoint"
    ea_counts = daily.ea_method.value_counts().to_dict()
    et0_missing = round(100 * float(daily.et0_mm.isna().mean()), 3)
    limits_e = [
        f"fuente de cálculo de ET0: {meta.get('et0_source')}",
        "ea_sensible_a_la_ruta no evaluada: tolerancia pendiente (DP-08)",
        "ET0 es un valor modelado, no una medición",
        "resolución de celda ~0.5°x0.625° [Verificar]",
    ]
    if vr:
        d = vr["et0_T2MDEW_vs_RH2M"]["mean_abs_diff_mm_day"]
        limits_e.append(f"diferencia media absoluta de ET0, T2MDEW vs RH2M: {d} mm/día")
    ev_et0 = r[rule_e]["evidence"]   # insumos meteorológicos de POWER: tope B
    et0_row = {
        "indicator_code": "et0_mm", "unit": "mm/día",
        "provenance": r[rule_e]["provenance"], "evidence": ev_et0, "rule": rule_e,
        "method": f"FAO56-PM; G=0; ea por días: {ea_counts}; radiación modelada: {rad_modeled_days} días",
        "missing_pct": et0_missing,
        "assumptions": ["G = 0 en paso diario", "presión atmosférica con la elevación indicada en curate (valor de prueba hasta tener el DEM)"],
        "limitations": limits_e,
    }

    # --- Pef por decena (mínimo entre lluvia y método; método sin cita aún) ---
    rule_pe = "pef_min_inputs"
    ev_pef = min_evidence(ev_precip, "C")   # método primario sin cita (DP-06) => C
    pef_row = {
        "indicator_code": "pef_mm", "unit": "mm/decena",
        "provenance": r[rule_pe]["provenance"], "evidence": ev_pef, "rule": rule_pe,
        "method": "Pef mensual (usda_scs_fao y fao_dependable) repartida por decena; upper_bound",
        "missing_pct": precip_missing,
        "assumptions": ["desagregación por decena = asignación, no proceso físico"],
        "limitations": [
            "fórmulas mensuales marcadas [Verificar] (DP-06)",
            "método primario sin justificación citada",
            "phi de fixed_fraction pendiente",
        ],
    }

    rows = []
    win = meta.get("imerg_window") if meta.get("precip_primary") == "IMERG_FINAL_V07" else None
    pw = (pd.Timestamp(win[0]).date(), pd.Timestamp(win[1]).date()) if win else period
    for row, hs in ((precip_row, precip_hashes), (et0_row, power_hashes), (pef_row, precip_hashes)):
        pr_ = pw if row["indicator_code"] in ("precip_mm", "pef_mm") else period
        row.update(period_start=pr_[0], period_end=pr_[1], raw_sha256=hs)
        rows.append(row)
    return rows


SQL_INSERT = """
INSERT INTO prov.indicator_provenance
    (run_id, indicator_code, unit, provenance, evidence_level, source_ids,
    ingestion_ids, dataset_version, period_start, period_end, temporal_res,
    processing_method, retrieved_at, missing_pct, assumptions, limitations,
    evidence_rule_id)
SELECT NULL, %(code)s, %(unit)s, %(prov)s::provenance_t, %(ev)s::evidence_t,
        %(sources)s::smallint[], %(ing)s::uuid[], NULL, %(ps)s, %(pe)s,
        interval '1 day', %(method)s,
        (SELECT max(queried_at) FROM prov.ingestion_run WHERE ingestion_id = ANY(%(ing)s::uuid[])),
        %(miss)s::real, %(assump)s::text[], %(limit)s::text[], %(rule)s
WHERE NOT EXISTS (
    SELECT 1 FROM prov.indicator_provenance
    WHERE run_id IS NULL AND indicator_code = %(code)s AND evidence_rule_id = %(rule)s
    AND ingestion_ids = %(ing)s::uuid[] AND period_start = %(ps)s AND period_end = %(pe)s)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--rules", default="catalogs/evidence_rules.yaml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rules = yaml.safe_load(Path(a.rules).read_text(encoding="utf-8"))
    try:
        rows = build_rows(a.zone, Path(a.data_dir), rules)
    except FileNotFoundError as e:
        print(f"ERROR: falta un archivo ({e.filename}). ¿Ejecutaste 'milpa_r1.py curate' para esa zona?",
                file=sys.stderr)
        return 2

    if a.dry_run:
        for r in rows:
            print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        print(f"\n(dry-run) {len(rows)} filas; no se escribió nada en la base")
        return 0

    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: define DATABASE_URL (variable de entorno o archivo .env)", file=sys.stderr)
        return 2
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("SELECT ingestion_id, source_id FROM prov.ingestion_run WHERE raw_sha256 = ANY(%s)",
                        (r["raw_sha256"],))
            found = cur.fetchall()
            if not found:
                print("ERROR: las ingestas no están en prov.ingestion_run (ejecuta cargar_manifiesto.py)",
                        file=sys.stderr)
                return 2
            ing = sorted({x[0] for x in found}, key=str)
            sids = sorted({x[1] for x in found})
            cur.execute(SQL_INSERT, {
                "code": r["indicator_code"], "unit": r["unit"], "prov": r["provenance"],
                "ev": r["evidence"], "sources": sids, "ing": ing,
                "ps": r["period_start"], "pe": r["period_end"], "method": r["method"],
                "miss": r["missing_pct"], "assump": r["assumptions"],
                "limit": r["limitations"], "rule": r["rule"]})
    print(f"{len(rows)} indicadores procesados (los ya existentes no se duplican)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
