#!/usr/bin/env python3
"""Carga un CSV de suelo SINTETICO (fixture) a soil.* para una parcela.

Cambios respecto a la version anterior (ver comentarios CAMBIO):
  * procedencia 'medido' con evidencia tope C (antes 'desconocido' sin evidencia)
  * regla de evidencia 'soil_fixture_c'
  * representatividad 'parcela' (antes 'desconocida', que la vista
    soil.property_status convierte en 'no_representativo')
Este script es SOLO para fixtures sinteticos (fuente SOIL_CSV_FIXTURE).
No lo uses para analisis reales de laboratorio: esos necesitan otra regla
de evidencia, metodo aceptado y representatividad verificada.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import date
from pathlib import Path

import psycopg

PROPERTIES = {
    "ph": ("ph", "ph_method", "pH", 3, 10),
    "organic_matter": ("om_pct", "om_method", "%", 0, 100),
    "sand": ("sand_pct", "texture_method", "%", 0, 100),
    "silt": ("silt_pct", "texture_method", "%", 0, 100),
    "clay": ("clay_pct", "texture_method", "%", 0, 100),
    "cec": ("cec_cmol_kg", "cec_method", "cmol/kg", 0, 200),
    "effective_depth": ("effective_root_depth_cm", None, "cm", 0, 1000),
    "awc": ("awc_mm_per_m", "awc_method", "mm/m", 0, 400),
}

# CAMBIO: constantes del fixture
FIXTURE_RULE_ID = "soil_fixture_c"
FIXTURE_LIMITATIONS = [
    "Fixture sintético: no representa un suelo real",
    "No usar para recomendaciones agronómicas ni validación científica",
]


def prepare(path, parcel):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    prepared = []
    errors = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            if row.get("parcel_code", "").strip() != parcel:
                errors.append(f"Fila {line}: parcela incorrecta")
                continue
            try:
                sampled = date.fromisoformat(row["sample_date"])
                d1, d2 = int(row["depth_from_cm"]), int(row["depth_to_cm"])
                if sampled > date.today() or d1 < 0 or d2 <= d1:
                    raise ValueError()
            except (ValueError, TypeError, KeyError):
                errors.append(f"Fila {line}: fecha o profundidad inválida")
                continue

            values = []
            for prop, (col, mcol, unit, lo, hi) in PROPERTIES.items():
                raw = (row.get(col) or "").strip()
                if not raw:
                    continue
                try:
                    value = float(raw)
                    if not lo <= value <= hi:
                        raise ValueError()
                except ValueError:
                    errors.append(f"Fila {line}: valor inválido en {col}")
                    continue
                method = (row.get(mcol) or "").strip() if mcol else "declarado/medido"
                if not method:
                    errors.append(f"Fila {line}: falta método para {col}")
                    continue
                values.append((prop, value, unit, method))

            texture = [(row.get(c) or "").strip()
                        for c in ("sand_pct", "silt_pct", "clay_pct")]
            if any(texture):
                if not all(texture):
                    errors.append(f"Fila {line}: textura incompleta")
                else:
                    try:
                        nums = [float(x) for x in texture]
                        if any(not 0 <= x <= 100 for x in nums) or abs(sum(nums)-100) > 2:
                            errors.append(f"Fila {line}: textura fuera de rango o suma incorrecta")
                    except ValueError:
                        errors.append(f"Fila {line}: textura no numérica")

            prepared.append({
                "line": line, "date": sampled, "d1": d1, "d2": d2,
                "lab": (row.get("lab") or "").strip() or None,
                "values": values
            })

    return digest, prepared, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parcel", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    path = Path(a.file)
    digest, rows, errors = prepare(path, a.parcel)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    total = sum(len(r["values"]) for r in rows)
    print(f"SHA-256: {digest}")
    print(f"Muestras: {len(rows)} | Mediciones: {total}")
    # CAMBIO
    print("Procedencia: medido, evidencia C (fixture sintético)")

    if a.dry_run:
        print("DRY-RUN: sin cambios")
        return 0

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está configurada")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT parcel_id FROM farm.parcel WHERE code=%s", (a.parcel,))
            found = cur.fetchone()
            if not found:
                raise RuntimeError(f"No existe parcela {a.parcel}")
            parcel_id = found[0]

            cur.execute("""
                SELECT ingestion_id FROM prov.ingestion_run
                WHERE source_id=(SELECT source_id FROM prov.data_source WHERE code='SOIL_CSV_FIXTURE')
                    AND raw_sha256=%s
                    AND query_params->>'parcel'=%s
            """, (digest, a.parcel))
            if cur.fetchone():
                print("Esta parcela y archivo ya fueron importados. Sin cambios.")
                return 0

            cur.execute("""
                SELECT source_id FROM prov.data_source WHERE code='SOIL_CSV_FIXTURE'
            """)
            source = cur.fetchone()
            if not source:
                raise RuntimeError("No existe SOIL_CSV_FIXTURE")
            sid = source[0]

            cur.execute("""
                INSERT INTO prov.ingestion_run
                (source_id, query_params, period_start, period_end,
                raw_uri, raw_sha256, n_records, status, report)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'ok',%s)
                RETURNING ingestion_id
            """, (
                sid, json.dumps({"parcel": a.parcel, "file": path.name}),
                min(r["date"] for r in rows), max(r["date"] for r in rows),
                str(path.resolve()), digest, total,
                json.dumps({"synthetic_fixture": True, "sample_count": len(rows)})
            ))
            ingestion_id = cur.fetchone()[0]

            inserted = 0
            for r in rows:
                cur.execute("""
                    INSERT INTO soil.sample
                    (parcel_id, sampled_at, lab, depth_from_cm, depth_to_cm, ingestion_id)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING sample_id
                """, (parcel_id, r["date"], r["lab"], r["d1"], r["d2"], ingestion_id))
                sample_id = cur.fetchone()[0]

                for prop, value, unit, method in r["values"]:
                    # CAMBIO: provenance 'medido', evidencia tope C, regla soil_fixture_c
                    cur.execute("""
                        INSERT INTO prov.indicator_provenance
                        (indicator_code, unit, provenance, evidence_level,
                        source_ids, ingestion_ids, processing_method,
                        assumptions, limitations, evidence_rule_id)
                        VALUES (%s,%s,'medido','C',%s,%s,%s,%s,%s,%s)
                        RETURNING ip_id
                    """, (
                        f"soil_{prop}", unit, [sid], [ingestion_id],
                        f"CSV fixture sintético; método declarado: {method}",
                        ["Datos sintéticos internos, no proceden de análisis real"],
                        FIXTURE_LIMITATIONS,
                        FIXTURE_RULE_ID
                    ))
                    ip_id = cur.fetchone()[0]

                    # CAMBIO: representatividad 'parcela' (supuesto del fixture).
                    # Con 'desconocida' la vista devuelve 'no_representativo'.
                    cur.execute("""
                        INSERT INTO soil.measurement
                        (sample_id, property_code, value, unit, method,
                        representativeness, ip_id)
                        VALUES (%s,%s,%s,%s,%s,'parcela',%s)
                    """, (sample_id, prop, value, unit, method, ip_id))
                    inserted += 1

    print(f"Importación completada: {len(rows)} muestras, {inserted} mediciones.")


if __name__ == "__main__":
    raise SystemExit(main())
