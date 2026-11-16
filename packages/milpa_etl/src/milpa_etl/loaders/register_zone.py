#!/usr/bin/env python3
"""
registrar_zona.py — registra una zona de análisis en PostGIS (esquema geo):
geo.region, geo.zone, geo.climate_cell y geo.zone_cell.

    - La zona viene de un GeoJSON (Polygon) APROXIMADO; no contiene parcelas.
    - De POWER se lee del JSON crudo (geometry.coordinates) el PUNTO DE CONSULTA y la
    altitud que devuelve. Son las coordenadas solicitadas, NO el centro de la celda.
    - POWER se consulta una vez por zona (apartado 9 del PDF): la zona queda
    representada por ese punto con peso 1.0. La huella de la celda se guarda como
    aproximada (centrada en el punto, no alineada a la rejilla real) [Verificar].

Uso:
    python registrar_zona.py --zone chiquimula_prueba --geojson zona_chiquimula_prueba.geojson \
        --region-config region_pack.yml --dry-run
    python registrar_zona.py --zone chiquimula_prueba --geojson zona_chiquimula_prueba.geojson \
        --region-config region_pack.yml
Requiere DATABASE_URL (variable de entorno o archivo .env) y, sin --dry-run, psycopg.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Tamaño asumido de la celda de POWER (MERRA-2): 0.5° lat x 0.625° lon. [Verificar] DP-16
CELL_LAT_DEG = 0.5
CELL_LON_DEG = 0.625


def load_env(path=".env"):
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_power_cell(zone: str, data_dir: Path) -> dict:
    mf = data_dir / "manifest" / "ingestions.jsonl"
    if not mf.exists():
        raise SystemExit("ERROR: no existe el manifiesto; ejecuta fetch-power primero")
    entries = [json.loads(x) for x in mf.read_text(encoding="utf-8").splitlines() if x.strip()]
    entries = [e for e in entries if e["source"] == "POWER_DAILY"
                and e["params"].get("zone") == zone and e["status"] == "ok"]
    if not entries:
        raise SystemExit(f"ERROR: no hay ingesta POWER ok para la zona {zone}")
    data = json.loads(Path(entries[-1]["raw_uri"]).read_text(encoding="utf-8"))
    coords = (data.get("geometry") or {}).get("coordinates")
    if not coords or len(coords) < 2:
        raise SystemExit("ERROR: la respuesta de POWER no trae geometry.coordinates; "
                        "indícame cómo viene en tu JSON crudo y lo ajusto")
    lon, lat = float(coords[0]), float(coords[1])
    elev = float(coords[2]) if len(coords) > 2 else None
    return {"lon": lon, "lat": lat, "grid_elevation_m": elev}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--geojson", required=True)
    ap.add_argument("--region-config", required=True, help="region pack YAML (para config_hash)")
    ap.add_argument("--region-code", default="pilot_corredor_seco")
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--dry-run", action="store_true")
    # Alternativa documentada: sin manifiesto de descargas (los JSON crudos no se versionan) se pueden
    # indicar las coordenadas que se solicitaron a POWER (las mismas de `fetch power --lat --lon`).
    ap.add_argument("--lat", type=float, default=None, help="latitud solicitada a POWER")
    ap.add_argument("--lon", type=float, default=None, help="longitud solicitada a POWER")
    a = ap.parse_args()

    feat = json.loads(Path(a.geojson).read_text(encoding="utf-8"))
    geom = feat["geometry"] if feat.get("type") == "Feature" else feat
    if geom["type"] != "Polygon":
        raise SystemExit("ERROR: el GeoJSON debe ser un Polygon")
    cfg = Path(a.region_config)
    if not cfg.exists():
        raise SystemExit(f"ERROR: no existe {cfg}")
    if (a.lat is None) != (a.lon is None):
        raise SystemExit("ERROR: --lat y --lon van juntos")
    if a.lat is not None:
        cell = {"lat": a.lat, "lon": a.lon, "grid_elevation_m": None}
    else:
        cell = read_power_cell(a.zone, Path(a.data_dir))

    print(f"Punto de consulta POWER (coordenadas solicitadas): lat {cell['lat']}, lon {cell['lon']}")
    print(f"Altitud que devuelve POWER: {cell['grid_elevation_m']} m (no es la del DEM del sitio)")
    print(f"Huella aproximada: {CELL_LAT_DEG}° x {CELL_LON_DEG}° centrada en el punto [Verificar]")
    if a.dry_run:
        print("(dry-run) no se escribió nada en la base")
        return 0

    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ERROR: define DATABASE_URL (variable de entorno o .env)")
    import psycopg

    gj = json.dumps(geom)
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT source_id FROM prov.data_source WHERE code = 'POWER_DAILY'")
        row = cur.fetchone()
        if not row:
            raise SystemExit("ERROR: falta POWER_DAILY en prov.data_source (ejecuta el seed)")
        sid = row[0]

        cur.execute("""
            INSERT INTO geo.region (code, name, config_uri, config_hash, bbox)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_Envelope(ST_GeomFromGeoJSON(%s)), 4326))
            ON CONFLICT (code) DO NOTHING""",
            (a.region_code, a.region_code, str(cfg), sha256_file(cfg), gj))
        cur.execute("SELECT region_id FROM geo.region WHERE code = %s", (a.region_code,))
        region_id = cur.fetchone()[0]

        cur.execute("SELECT zone_id FROM geo.zone WHERE name = %s AND region_id = %s", (a.zone, region_id))
        z = cur.fetchone()
        if z:
            zone_id = z[0]
            print("La zona ya existía; no se duplica")
        else:
            cur.execute("""
                INSERT INTO geo.zone (region_id, name, geom)
                VALUES (%s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                RETURNING zone_id""", (region_id, a.zone, gj))
            zone_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO geo.climate_cell (source_id, centroid, footprint)
            VALUES (%(s)s, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
                    ST_MakeEnvelope(%(lon)s - %(hl)s, %(lat)s - %(ha)s,
                                    %(lon)s + %(hl)s, %(lat)s + %(ha)s, 4326))
            ON CONFLICT (source_id, centroid) DO NOTHING""",
            {"s": sid, "lon": cell["lon"], "lat": cell["lat"],
            "hl": CELL_LON_DEG / 2, "ha": CELL_LAT_DEG / 2})
        cur.execute("""SELECT cell_id FROM geo.climate_cell
                        WHERE source_id = %s AND centroid = ST_SetSRID(ST_MakePoint(%s, %s), 4326)""",
                    (sid, cell["lon"], cell["lat"]))
        cell_id = cur.fetchone()[0]

        cur.execute("""INSERT INTO geo.zone_cell (zone_id, cell_id, weight) VALUES (%s, %s, 1.0)
                        ON CONFLICT (zone_id, cell_id) DO UPDATE SET weight = EXCLUDED.weight""",
                    (zone_id, cell_id))
        print("zone_cell registrado con peso 1.0 (zona representada por un solo punto de POWER)")
        print("AVISO: la huella de la celda es aproximada, no alineada a la rejilla real de POWER [Verificar]")
    print("zona registrada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
