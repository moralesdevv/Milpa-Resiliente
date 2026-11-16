"""Importa la serie diaria IMERG (GIS V07B, celda de 0,1°) extraída por R2 al formato raw de R1.

Entrada: ``imerg_final_daily_v07b_camotan_jocotan_2001_2025-09.csv`` (paquete
``MILPA_RESILIENTE_R2_Motor_Cientifico``): una fila por día y punto de referencia (Camotán y Jocotán caen
en la MISMA celda, así que se usa una sola) con ``precipitation_mm`` y ``quality_status``.

UNIDADES (verificado en los metadatos de los GeoTIFF: ``Unit=0.1(mm/hr) ScaleFactor=10``, archivo
``…total.rate.tif``): el entero guardado es 10 × la TASA media (mm/h) del día; la columna ``precipitation_mm``
del CSV es esa tasa (``entero*0.1``) y NO un acumulado. El acumulado diario es ``tasa × 24 h``. Este script
aplica ese factor (comprobación independiente: con ×24 el total anual de IMERG ≈ 1,03 × el de POWER).

Salida: un raw JSON zonal (el formato que R1 lee en ``load_imerg_series``) + una entrada en el manifiesto
de ingestas con su SHA-256. Después, ``milpa-etl merge imerg --zone <zona>`` hace la fusión con las reglas
de R1 (IMERG primaria, POWER de respaldo con bit 32). Este script NO inventa ni rellena valores: un día sin
estado ``valid`` queda faltante.

    DATA_DIR=./data python tools/r2/import_imerg_csv.py --csv <archivo.csv> --zone camotan_jocotan
    DATA_DIR=./data milpa-etl merge imerg --zone camotan_jocotan
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HOURS_PER_DAY = 24.0
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "milpa_etl" / "src"))

from milpa_etl import core as r1  # noqa: E402


def build_raw(csv: Path) -> tuple[dict, dict]:
    df = pd.read_csv(csv, dtype={"quality_status": str})
    cells = df[["latitude", "longitude", "row", "column"]].drop_duplicates(["row", "column"])
    if len(cells) != 1:
        raise SystemExit(f"se esperaba una sola celda IMERG y hay {len(cells)}: no se importa")
    # Los puntos de referencia comparten celda: el valor diario debe ser idéntico entre ellos.
    by_day = df.groupby("date")["precipitation_mm"].agg(["min", "max", "count"])
    if (by_day["max"] - by_day["min"]).abs().max() > 1e-9:
        raise SystemExit(
            "los puntos de la misma celda difieren en algún día: revisar la extracción"
        )
    first = df.sort_values("date").drop_duplicates("date", keep="first")
    valid = first["quality_status"].str.lower().eq("valid") & first["precipitation_mm"].notna()
    daily_mm = (
        first["precipitation_mm"] * HOURS_PER_DAY
    )  # tasa media (mm/h) -> acumulado diario (mm)
    rows = [
        {
            "date": d,
            "precip_mm": float(p) if ok else None,
            "n_valid_cells": 1 if ok else 0,
        }
        for d, p, ok in zip(first["date"], daily_mm, valid, strict=True)
    ]
    cell = cells.iloc[0]
    raw = {
        "product": "GPM IMERG daily GIS, V07B (3B-DAY-GIS.MS.MRG.3IMERG)",
        "cells": [
            {
                "lat": float(cell["latitude"]),
                "lon": float(cell["longitude"]),
                "row": int(cell["row"]),
                "col": int(cell["column"]),
            }
        ],
        "rows": rows,
    }
    report = {
        "n_days": len(rows),
        "n_valid_days": int(valid.sum()),
        "first": rows[0]["date"],
        "last": rows[-1]["date"],
        "unit_conversion": "precipitation_mm del CSV = tasa media (mm/h) (GeoTIFF Unit=0.1(mm/hr)); acumulado diario = tasa x 24",
        "note": "Extracción de R2 (paquete MILPA_RESILIENTE_R2_Motor_Cientifico). Producto/nivel (Final Run) según el nombre de archivo [Verificar].",
    }
    return raw, report


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--csv", required=True)
    ap.add_argument("--zone", required=True)
    a = ap.parse_args()
    raw, report = build_raw(Path(a.csv))
    text = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    out_dir = r1.DATA_DIR / "raw" / "imerg"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / sha
    path.write_text(text, encoding="utf-8")
    r1.log_ingestion(
        source="IMERG_FINAL_V07",
        product="GPM IMERG daily GIS V07B (extracción de R2)",
        version="V07B",
        params={"zone": a.zone, "origin": "r2_csv_import", "csv": Path(a.csv).name},
        raw_uri=path,
        raw_sha256=sha,
        n_records=len(raw["rows"]),
        status="ok",
        report=report,
    )
    print(json.dumps({"raw_sha256": sha, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
