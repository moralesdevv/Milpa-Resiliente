#!/usr/bin/env python3
"""
verificar_power_raw.py — ¿los días extremos de lluvia de POWER vienen tal cual de NASA o los produjo el pipeline?
Lee el JSON crudo (inmutable) de la última ingesta POWER_DAILY y muestra PRECTOTCORR sin transformar.
No modifica nada.   Uso:  python verificar_power_raw.py [--data-dir data] [--umbral 100]
"""
import argparse, json, sys
from pathlib import Path

FECHAS = ["20230109", "20230108", "20220506", "20220505", "20220306", "20220305", "20210528", "20210527"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--umbral", type=float, default=100.0)
    a = ap.parse_args()
    man = Path(a.data_dir) / "manifest" / "ingestions.jsonl"
    if not man.exists():
        print(f"ERROR: no existe {man}", file=sys.stderr); return 2
    ents = [json.loads(l) for l in man.read_text(encoding="utf-8").splitlines() if l.strip()]
    ents = [e for e in ents if e.get("source") == "POWER_DAILY" and e.get("status") in ("ok", "partial")]
    if not ents:
        print("ERROR: no hay ingestas POWER_DAILY en el manifiesto", file=sys.stderr); return 2
    e = ents[-1]
    p = Path(e["raw_uri"])
    if not p.exists():
        p = Path(a.data_dir) / "raw" / "power" / e["raw_sha256"]
    raw = json.loads(p.read_text(encoding="utf-8"))
    pr = raw["properties"]["parameter"]["PRECTOTCORR"]
    print(f"archivo: {p}\nsha256 : {e['raw_sha256']}\nparámetro: PRECTOTCORR  ({len(pr)} días)\n")
    print("Valores CRUDOS en las fechas sospechosas (mm/día):")
    for f in FECHAS:
        print(f"  {f[:4]}-{f[4:6]}-{f[6:]}  {pr.get(f, 'sin dato')}")
    vals = {k: v for k, v in pr.items() if v != -999}
    top = sorted(vals.items(), key=lambda kv: kv[1], reverse=True)[:10]
    print("\nLos 10 valores más altos del crudo:")
    for k, v in top:
        print(f"  {k[:4]}-{k[4:6]}-{k[6:]}  {v}")
    n = sum(1 for v in vals.values() if v >= a.umbral)
    print(f"\nDías con >= {a.umbral:g} mm: {n} de {len(vals)}")
    print("\nSi estos valores salen iguales aquí, son de NASA POWER (no un error del pipeline).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
