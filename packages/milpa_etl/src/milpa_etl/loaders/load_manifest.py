#!/usr/bin/env python3
"""
cargar_manifiesto.py — carga data/manifest/ingestions.jsonl en prov.ingestion_run.

Versión general: busca el source_id por el código de cada entrada (POWER_DAILY,
IMERG_FINAL_V07, ...), así que sirve para cualquier fuente ya dada de alta en
prov.data_source. Es idempotente: no repite una ingesta con el mismo raw_sha256.

Credenciales: DATABASE_URL (variable de entorno o archivo .env). Sin valor por defecto.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Json


def load_env(path=".env"):
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# Nombres con los que una fuente puede aparecer en el manifiesto -> código en prov.data_source
ALIASES = {"IMERG_FINAL": "IMERG_FINAL_V07"}


def as_date(v):
    """Acepta 'YYYY-MM-DD' o 'YYYYMMDD'; devuelve None si no hay valor."""
    if not v:
        return None
    v = str(v)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def main():
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("ERROR: define DATABASE_URL (variable de entorno o archivo .env)")
    manifest = Path(os.environ.get("DATA_DIR", "data")) / "manifest" / "ingestions.jsonl"
    if not manifest.exists():
        sys.exit(f"ERROR: no existe {manifest}")

    nuevas = omitidas = sin_fuente = 0
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT code, source_id FROM prov.data_source")
        ids = dict(cur.fetchall())
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("status") not in ("ok", "partial") or not e.get("raw_sha256"):
                continue
            sid = ids.get(ALIASES.get(e["source"], e["source"]))
            if sid is None:
                sin_fuente += 1
                print(f"AVISO: la fuente {e['source']!r} no está en prov.data_source; se omite")
                continue
            p = e.get("params", {})
            cur.execute("""
                INSERT INTO prov.ingestion_run
                    (source_id, query_params, queried_at, period_start, period_end,
                    raw_uri, raw_sha256, n_records, status, report)
                SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                WHERE NOT EXISTS (SELECT 1 FROM prov.ingestion_run WHERE raw_sha256 = %s)
            """, (sid, Json(p), e["queried_at"],
                    as_date(p.get("period_start") or p.get("start")),
                    as_date(p.get("period_end") or p.get("end")),
                    e["raw_uri"], e["raw_sha256"], e.get("n_records"), e["status"],
                    Json(e["report"]) if e.get("report") else None, e["raw_sha256"]))
            if cur.rowcount:
                nuevas += 1
            else:
                omitidas += 1
    print(f"manifiesto cargado: {nuevas} nuevas, {omitidas} ya existían, {sin_fuente} sin fuente")


if __name__ == "__main__":
    main()
