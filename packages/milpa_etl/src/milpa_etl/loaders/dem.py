#!/usr/bin/env python3
"""fetch_dem.py — DEM Copernicus GLO-30 -> elevación y pendiente de la zona.

    Qué hace (MILPA RESILIENTE 3.3, §8-§9):
    1. Descarga las teselas de 1° x 1° que cubren el polígono de la zona
        (o usa archivos locales con --tif). Guarda cada tesela cruda en
        data/raw/DEM_30M/<sha256>.tif (inmutable, direccionada por hash).
    2. Calcula elevación media y pendiente media (%) dentro del polígono.
    3. Registra la diferencia con la altitud de la rejilla de POWER.
    4. En la base: prov.data_source (si falta DEM_30M), prov.ingestion_run,
        prov.indicator_provenance y actualiza geo.zone (elevation_m,
        slope_pct, ip_elevation).

    Uso:
    python fetch_dem.py --zone chiquimula_prueba --geojson zona_chiquimula_prueba.geojson --dry-run
    python fetch_dem.py --zone chiquimula_prueba --geojson zona_chiquimula_prueba.geojson
    Conexión: --database-url o DATABASE_URL (la misma de seed_catalogo.py).
    Sin red:  añade --tif archivo.tif [otro.tif ...] para usar teselas ya descargadas.

    Todo lo marcado [Verificar] debe confirmarse en la ficha oficial del producto.
    """
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

import numpy as np
import psycopg
from psycopg.types.numeric import FloatDumper, IntDumper


class _NpFloat(FloatDumper):
    def dump(self, obj):
        return super().dump(float(obj))


class _NpInt(IntDumper):
    def dump(self, obj):
        return super().dump(int(obj))


# psycopg 3 no adapta escalares NumPy por sí solo (psycopg2 usaba register_adapter)
for _t in (np.float32, np.float64):
    psycopg.adapters.register_dumper(_t, _NpFloat)
for _t in (np.int32, np.int64):
    psycopg.adapters.register_dumper(_t, _NpInt)

# [Verificar] patrón de URL del bucket público de Copernicus DEM GLO-30 (COG).
TILE_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
SOURCE_CODE = "DEM_30M"
PRODUCT = "Copernicus GLO-30 DEM (COG)"       # [Verificar] nombre y versión
INSTITUTION = "ESA / Copernicus"
LICENSE_NOTE = "[Verificar] licencia Copernicus DEM"
# Regla de evidencia: nombre provisional; debe existir en evidence_rules.yaml.
EVIDENCE_RULE_ID = "dem_elevation_b"


# ---------- geometría ----------
def read_geometry(path):
    with open(path, encoding="utf-8") as f:
        g = json.load(f)
    t = g.get("type")
    if t == "FeatureCollection":
        geoms = [ft["geometry"] for ft in g["features"]]
    elif t == "Feature":
        geoms = [g["geometry"]]
    else:
        geoms = [g]
    geoms = [x for x in geoms if x and x["type"] in ("Polygon", "MultiPolygon")]
    if not geoms:
        sys.exit("ERROR: el GeoJSON no tiene Polygon ni MultiPolygon.")
    return geoms


def flat_coords(node):
    if isinstance(node, (list, tuple)) and node and isinstance(node[0], (int, float)):
        yield node
    else:
        for n in node:
            yield from flat_coords(n)


def bbox_of(geoms):
    pts = [p for g in geoms for p in flat_coords(g["coordinates"])]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ---------- teselas ----------
def tile_name(lat, lon):
    ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
    ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def tiles_for(bbox):
    w, s, e, n = bbox
    out = []
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            out.append((lat, lon, tile_name(lat, lon)))
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_tile(name, raw_dir):
    url = TILE_URL.format(name=name)
    os.makedirs(raw_dir, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=raw_dir, suffix=".part")
    tmp.close()
    print(f"Descargando {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp.name, "wb") as out:
            shutil.copyfileobj(r, out)
    except Exception as exc:
        os.unlink(tmp.name)
        sys.exit(f"ERROR al descargar {url}: {exc}\n"
                "Verifica el patrón de URL [Verificar] o usa --tif con teselas locales.")
    return tmp.name, url


def store_raw(path, raw_dir):
    """Copia a data/raw/DEM_30M/<sha256>.tif si no existe. Devuelve (ruta, sha)."""
    sha = sha256_file(path)
    os.makedirs(raw_dir, exist_ok=True)
    dest = os.path.join(raw_dir, f"{sha}.tif")
    if not os.path.exists(dest):
        shutil.copyfile(path, dest)
    return dest, sha


# ---------- cálculo ----------
def zonal_stats(tif_paths, geoms, bbox):
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.merge import merge

    datasets = [rasterio.open(p) for p in tif_paths]
    try:
        res = datasets[0].res  # (x, y) en grados
        pad_x, pad_y = 2 * res[0], 2 * res[1]
        w, s, e, n = bbox
        bounds = (w - pad_x, s - pad_y, e + pad_x, n + pad_y)
        nodata = datasets[0].nodata if datasets[0].nodata is not None else -9999.0
        arr, transform = merge(datasets, bounds=bounds, nodata=nodata)
    finally:
        for d in datasets:
            d.close()

    z = arr[0].astype("float64")
    z[z == nodata] = np.nan

    inside = geometry_mask(geoms, out_shape=z.shape, transform=transform, invert=True)
    note = None
    if inside.sum() == 0:
        inside = geometry_mask(geoms, out_shape=z.shape, transform=transform,
                                invert=True, all_touched=True)
        note = "polígono menor que un píxel: se usó all_touched"
    if inside.sum() == 0:
        sys.exit("ERROR: el polígono no cubre ningún píxel del DEM.")

    lat0 = (bounds[1] + bounds[3]) / 2
    dx = abs(transform.a) * 111320.0 * math.cos(math.radians(lat0))
    dy = abs(transform.e) * 110574.0
    gy, gx = np.gradient(z, dy, dx)
    slope_pct = np.hypot(gx, gy) * 100.0

    vals = z[inside]
    valid = ~np.isnan(vals)
    sl = slope_pct[inside]
    sl_valid = ~np.isnan(sl)
    if valid.sum() == 0:
        sys.exit("ERROR: todos los píxeles dentro del polígono son nodata.")
    return {
        "n_pixels": int(inside.sum()),
        "n_valid": int(valid.sum()),
        "missing_pct": round(100.0 * (1 - valid.sum() / inside.sum()), 3),
        "elev_mean": float(np.nanmean(vals)),
        "elev_min": float(np.nanmin(vals)),
        "elev_max": float(np.nanmax(vals)),
        "elev_std": float(np.nanstd(vals)),
        "slope_mean_pct": float(np.nanmean(sl)) if sl_valid.any() else None,
        "pixel_m": (round(dx, 1), round(dy, 1)),
        "note": note,
    }


# ---------- base de datos ----------

def write_db(url, zone, stats, tiles, power_elev, diff):
    from psycopg.types.json import Json

    conn = psycopg.connect(url)

    try:
        with conn, conn.cursor() as cur:

            # Buscar zona
            cur.execute(
                "SELECT zone_id FROM geo.zone WHERE name = %s",
                (zone,)
            )
            row = cur.fetchone()

            if not row:
                sys.exit(
                    f"ERROR: no existe la zona {zone!r} en geo.zone. "
                    "Corre antes registrar_zona.py."
                )

            zone_id = row[0]

            # Buscar o crear fuente de datos
            cur.execute(
                "SELECT source_id FROM prov.data_source WHERE code = %s",
                (SOURCE_CODE,)
            )
            r = cur.fetchone()

            if r:
                source_id = r[0]
            else:
                cur.execute(
                    "SELECT COALESCE(MAX(source_id), 0) + 1 "
                    "FROM prov.data_source"
                )
                source_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO prov.data_source
                        (source_id, code, product_name, institution, is_nasa,
                        version, spatial_res_m, license, redistributable,
                        access_url)
                    VALUES (%s,%s,%s,%s,false,%s,30,%s,false,%s)
                    """,
                    (
                        source_id,
                        SOURCE_CODE,
                        PRODUCT,
                        INSTITUTION,
                        "[Verificar]",
                        LICENSE_NOTE,
                        TILE_URL
                    )
                )

                print(
                    f"Se creó prov.data_source {SOURCE_CODE} "
                    f"(source_id={source_id})."
                )

            # Registrar ingestiones
            ing_ids = []

            for t in tiles:
                cur.execute(
                    """
                    INSERT INTO prov.ingestion_run
                        (source_id, query_params, period_start, period_end,
                        raw_uri, raw_sha256, n_records, status, report)
                    VALUES (%s,%s,NULL,NULL,%s,%s,%s,'ok',%s)
                    RETURNING ingestion_id
                    """,
                    (
                        source_id,
                        Json({
                            "zone": zone,
                            "tile": t["name"],
                            "url": t["url"]
                        }),
                        t["raw_uri"],
                        t["sha256"],
                        stats["n_pixels"],
                        Json({
                            "descarga_utc":
                                datetime.now(timezone.utc).isoformat()
                        })
                    )
                )

                ing_ids.append(cur.fetchone()[0])

            # Supuestos
            assumptions = [
                "elevación = media de píxeles dentro del polígono de la zona",
                (
                    f"pendiente media (%) por gradiente sobre píxeles de "
                    f"~{stats['pixel_m'][0]} x {stats['pixel_m'][1]} m"
                ),
                (
                    f"altitud de rejilla POWER de referencia: {power_elev} m; "
                    f"diferencia DEM - POWER = {diff:+.2f} m"
                ),
            ]

            # Limitaciones
            limitations = [
                "DEM de superficie (puede incluir dosel y construcciones)",
                "una zona no es una parcela",
            ]

            if stats["note"]:
                limitations.append(stats["note"])

            # Registrar procedencia del indicador
            cur.execute(
                """
                INSERT INTO prov.indicator_provenance
                    (run_id, indicator_code, unit, provenance,
                    evidence_level, source_ids, ingestion_ids,
                    dataset_version, spatial_res_m,
                    processing_method, retrieved_at, missing_pct,
                    assumptions, limitations, evidence_rule_id)
                VALUES (
                    NULL,
                    'zone_elevation_mean',
                    'm',
                    'satelital',
                    'B',
                    %s,
                    ARRAY[%s::uuid],
                    %s,
                    30,
                    %s,
                    now(),
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING ip_id
                """,
                (
                    [source_id],
                    ing_ids[0] if ing_ids else None,
                    "[Verificar]",
                    "zonal mean sobre Copernicus GLO-30; pendiente por np.gradient",
                    stats["missing_pct"],
                    assumptions,
                    limitations,
                    EVIDENCE_RULE_ID
                )
            )

            ip_id = cur.fetchone()[0]

            # Actualizar zona
            cur.execute(
                """
                UPDATE geo.zone
                SET elevation_m=%s,
                    slope_pct=%s,
                    ip_elevation=%s
                WHERE zone_id=%s
                """,
                (
                    round(stats["elev_mean"], 2),
                    None if stats["slope_mean_pct"] is None
                    else round(stats["slope_mean_pct"], 2),
                    ip_id,
                    zone_id
                )
            )

        print("OK: geo.zone actualizada, con procedencia registrada.")

    finally:
        conn.close()



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--geojson", required=True)
    ap.add_argument("--tif", nargs="+", help="teselas locales (omite la descarga)")
    ap.add_argument("--power-elev", type=float, default=762.46,
                    help="altitud de rejilla de POWER para comparar (m)")
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--dry-run", action="store_true",
                    help="calcula y muestra, sin escribir en la base")
    a = ap.parse_args()

    try:
        import rasterio  # noqa: F401
    except ImportError:
        sys.exit("ERROR: falta rasterio (pip install rasterio).")

    geoms = read_geometry(a.geojson)
    bbox = bbox_of(geoms)
    print(f"bbox zona (lon/lat): {bbox}")

    raw_dir = os.path.join(a.data_dir, "raw", SOURCE_CODE)
    tiles, paths = [], []
    if a.tif:
        for p in a.tif:
            dest, sha = store_raw(p, raw_dir)
            tiles.append({"name": os.path.basename(p), "url": "local",
                            "raw_uri": dest, "sha256": sha})
            paths.append(dest)
    else:
        for lat, lon, name in tiles_for(bbox):
            tmp, url = download_tile(name, raw_dir)
            dest, sha = store_raw(tmp, raw_dir)
            os.unlink(tmp)
            tiles.append({"name": name, "url": url, "raw_uri": dest, "sha256": sha})
            paths.append(dest)

    stats = zonal_stats(paths, geoms, bbox)
    diff = stats["elev_mean"] - a.power_elev

    print("\n--- Resultado ---")
    print(f"Píxeles en la zona: {stats['n_pixels']}  (válidos: {stats['n_valid']}, "
            f"faltantes: {stats['missing_pct']} %)")
    print(f"Elevación media: {stats['elev_mean']:.2f} m  "
            f"(min {stats['elev_min']:.1f}, max {stats['elev_max']:.1f}, "
            f"desv. {stats['elev_std']:.1f})")
    sm = stats["slope_mean_pct"]
    print(f"Pendiente media: {'n/d' if sm is None else f'{sm:.2f} %'}")
    print(f"Altitud de rejilla POWER: {a.power_elev} m  ->  DEM - POWER = {diff:+.2f} m")
    for t in tiles:
        print(f"Tesela {t['name']}  sha256={t['sha256']}")
    if stats["note"]:
        print("Nota:", stats["note"])

    if a.dry_run:
        print("\n--dry-run: no se escribió nada en la base.")
        return
    if not a.database_url:
        sys.exit("ERROR: falta --database-url o la variable DATABASE_URL.")
    write_db(a.database_url, a.zone, stats, tiles, a.power_elev, diff)



if __name__ == "__main__":
    main()
