#!/usr/bin/env python3
"""
milpa_r1.py — Rol R1 (Datos y evidencia) de MILPA RESILIENTE 3.3, en un solo archivo.

Implementa (apartados 9, 11.3, 11.4, 11.14, 13.4 y 21 del documento de arquitectura):
    1. Manifiesto de ingestas con SHA-256 y capa raw inmutable.
    2. Conector NASA POWER (diario, por punto) con reintentos.
    3. Limpieza (clean): centinelas -> nulo, QC físico, qc_flags, relleno <= 3 días
        (la lluvia NUNCA se interpola), radiación modelada (Hargreaves-Samani).
    4. Curación (curated): ET0 FAO-56 PM (dos rutas de ea), precipitación efectiva
        (4 métodos), decenas, cobertura y data_hash.
    5. Validación: ET0 con T2MDEW vs RH2M; POWER vs estación (si existe).
    6. CSV de suelo por propiedad (celda vacía = no medido, nunca cero).
    7. Validador de catálogos y region pack ("sin cita no hay umbral").
    8. Paquete de demostración congelado con datos SINTÉTICOS rotulados + EXPECTED.json.
    9. Escáner de privacidad (coordenadas > 3 decimales y correos).

ESTADO: diseño implementado, NO validado contra datos reales. Todo lo marcado
[Verificar] / [Pendiente] debe confirmarse (DP-16, DP-06, DP-08...).
Pendiente de R2: milpa_core.climate es la fuente oficial de ET0/Pef; aquí hay una
implementación local de respaldo (se usa milpa_core si se puede importar).

Dependencias: pandas, numpy, requests, pyyaml. Opcional: pyarrow (Parquet).
Sin pyarrow, las tablas se escriben como CSV (misma estructura) y se avisa.

    Uso:  python milpa_r1.py selftest
        python milpa_r1.py --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import requests
except ImportError:  # solo se necesita para descargar
    requests = None
try:
    import yaml
except ImportError:
    yaml = None
try:
    import pyarrow  # noqa: F401
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
MILPA_MODE = os.environ.get("MILPA_MODE", "sandbox")  # sandbox | production

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_VARS = ["T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M", "WS2M",
            "ALLSKY_SFC_SW_DWN", "PRECTOTCORR"]
RENAME = {"T2M_MAX": "tmax_c", "T2M_MIN": "tmin_c", "T2MDEW": "tdew_c",
            "RH2M": "rh_pct", "WS2M": "wind2m_ms",
            "ALLSKY_SFC_SW_DWN": "srad_mj_m2", "PRECTOTCORR": "precip_mm"}
MET_VARS = ["tmax_c", "tmin_c", "tdew_c", "rh_pct", "wind2m_ms", "srad_mj_m2"]
ET0_INPUTS = ["tmax_c", "tmin_c", "wind2m_ms", "srad_mj_m2"]

# qc_flags (apartado 13.7)
F_MISSING, F_RANGE, F_GAPFILL, F_BIAS, F_RAD_MODEL, F_FALLBACK = 1, 2, 4, 8, 16, 32

MAX_GAP_FILL_DAYS = 3        # parámetro de 3.2 conservado (region.qc.max_gap_fill_days)
TDEW_TOL_C = 2.0             # [Pendiente] tolerancia tdew > tmean
HS_KRS = 0.16                # Hargreaves-Samani, zonas interiores (FAO-56). [Verificar]
PEFF_METHODS = ["usda_scs_fao", "fao_dependable", "fixed_fraction", "upper_bound"]


class ValidationFailed(Exception):
    pass


# ----------------------------------------------------------------------------
# Utilidades de E/S y hashes
# ----------------------------------------------------------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def logical_hash(df: pd.DataFrame) -> str:
    """Hash lógico de una tabla (independiente del formato de archivo)."""
    d = df.reset_index()
    d = d.reindex(sorted(d.columns), axis=1)
    csv = d.to_csv(index=False, float_format="%.6f", na_rep="NA")
    return sha256_bytes(csv.encode("utf-8"))


def write_table(df: pd.DataFrame, base: Path) -> Path:
    """Parquet si hay pyarrow; si no, CSV. `base` va sin extensión."""
    base.parent.mkdir(parents=True, exist_ok=True)
    if HAS_PARQUET:
        p = base.with_suffix(".parquet")
        df.to_parquet(p)
    else:
        p = base.with_suffix(".csv")
        df.to_csv(p)
    return p


def read_table(base: Path) -> pd.DataFrame:
    p = base.with_suffix(".parquet")
    if p.exists():
        return pd.read_parquet(p)
    p = base.with_suffix(".csv")
    df = pd.read_csv(p, index_col=0)
    if df.index.name == "obs_date":
        df.index = pd.to_datetime(df.index)
    return df


# ----------------------------------------------------------------------------
# 1. Manifiesto de ingestas (apartado 9)
# ----------------------------------------------------------------------------
def save_raw(source: str, content: bytes) -> tuple[str, Path]:
    """Raw inmutable, direccionado por hash: nunca se sobrescribe."""
    digest = sha256_bytes(content)
    path = DATA_DIR / "raw" / source / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return digest, path


def log_ingestion(*, source, product, version, params, raw_uri, raw_sha256,
                    n_records, status, report=None) -> dict:
    entry = {
        "source": source, "product": product, "version": version,
        "params": params,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "raw_uri": str(raw_uri), "raw_sha256": raw_sha256,
        "n_records": n_records, "status": status, "report": report,
    }
    mf = DATA_DIR / "manifest" / "ingestions.jsonl"
    mf.parent.mkdir(parents=True, exist_ok=True)
    with mf.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_manifest() -> list[dict]:
    mf = DATA_DIR / "manifest" / "ingestions.jsonl"
    if not mf.exists():
        return []
    return [json.loads(line) for line in mf.read_text(encoding="utf-8").splitlines() if line.strip()]


# ----------------------------------------------------------------------------
# 2. Conectores
# ----------------------------------------------------------------------------
def fetch_power(zone: str, lat: float, lon: float, start: str, end: str,
                retries: int = 4) -> dict:
    """Descarga POWER diario (comunidad AG). Se guarda el JSON completo."""
    if requests is None:
        raise RuntimeError("Falta el paquete 'requests'")
    # POWER usa una rejilla de ~0.5°: 2 decimales bastan y evitan coordenadas finas.
    lat, lon = round(lat, 2), round(lon, 2)
    query = {"parameters": ",".join(POWER_VARS), "community": "AG",
                "latitude": lat, "longitude": lon,
                "start": start.replace("-", ""), "end": end.replace("-", ""),
                "format": "JSON"}
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(POWER_URL, params=query, timeout=120)
            r.raise_for_status()
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == retries - 1:
                log_ingestion(source="POWER_DAILY", product="POWER daily AG", version=None,
                                params={**query, "zone": zone}, raw_uri="", raw_sha256="",
                                n_records=0, status="failed", report={"error": str(e)})
                raise
            time.sleep(2 ** attempt)  # backoff exponencial
    digest, path = save_raw("power", r.content)
    data = r.json()
    n = len(data["properties"]["parameter"][POWER_VARS[0]])
    # [Verificar] DP-16: dónde informa POWER la versión del producto.
    version = (data.get("header") or {}).get("api", {}).get("version") if isinstance(data.get("header"), dict) else None
    log_ingestion(source="POWER_DAILY", product="POWER daily AG", version=version,
                    params={**query, "zone": zone}, raw_uri=path, raw_sha256=digest,
                    n_records=n, status="ok")
    return data


# --- IMERG Final V07 diario (DP-16: producto/variable/unidades CONFIRMADOS con imerg_probe.py) ---
IMERG_SHORT_NAME = "GPM_3IMERGDF"
IMERG_VERSION = "07"
IMERG_VAR = "precipitation"          # mm/day; relleno -9999.9; dims (time, lon, lat)
IMERG_STEP = 0.1                     # grados
IMERG_LON0, IMERG_LAT0 = -179.95, -89.95   # centro de la celda (0, 0)
IMERG_FILL_LIMIT = -9000.0           # todo valor <= esto es relleno


def _flat_coords(node):
    if isinstance(node, (list, tuple)) and node and isinstance(node[0], (int, float)):
        yield node
    else:
        for n in node:
            yield from _flat_coords(n)


def read_polygons(path) -> list:
    """GeoJSON -> lista de polígonos; cada polígono = lista de anillos [[lon, lat], ...]."""
    g = json.loads(Path(path).read_text(encoding="utf-8"))
    t = g.get("type")
    geoms = ([f["geometry"] for f in g["features"]] if t == "FeatureCollection"
            else [g["geometry"]] if t == "Feature" else [g])
    polys = []
    for x in geoms:
        if x and x["type"] == "Polygon":
            polys.append(x["coordinates"])
        elif x and x["type"] == "MultiPolygon":
            polys.extend(x["coordinates"])
    if not polys:
        raise ValidationFailed("el GeoJSON no tiene Polygon ni MultiPolygon")
    return polys


def _in_ring(px, py, ring) -> np.ndarray:
    x = np.array([p[0] for p in ring], float)
    y = np.array([p[1] for p in ring], float)
    inside = np.zeros(px.shape, bool)
    j = len(x) - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        for i in range(len(x)):
            cond = ((y[i] > py) != (y[j] > py)) & \
                   (px < (x[j] - x[i]) * (py - y[i]) / (y[j] - y[i]) + x[i])
            inside ^= cond
            j = i
    return inside


def _in_polygons(px, py, polys) -> np.ndarray:
    out = np.zeros(px.shape, bool)
    for rings in polys:
        ins = np.zeros(px.shape, bool)
        for ring in rings:            # par-impar: los huecos restan
            ins ^= _in_ring(px, py, ring)
        out |= ins
    return out


def imerg_cells(polys, sub: int = 20) -> list[dict]:
    """Celdas IMERG que cubren la zona. peso = fracción del área de la zona que cae
    en cada celda (suma 1). Área por muestreo sub x sub dentro de cada celda."""
    pts = np.array([p[:2] for pl in polys for r in pl for p in r], float)
    w, s, e, n = pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()
    half = IMERG_STEP / 2
    i_lo = int(math.floor((w - (IMERG_LON0 - half)) / IMERG_STEP))
    i_hi = int(math.floor((e - (IMERG_LON0 - half)) / IMERG_STEP))
    j_lo = int(math.floor((s - (IMERG_LAT0 - half)) / IMERG_STEP))
    j_hi = int(math.floor((n - (IMERG_LAT0 - half)) / IMERG_STEP))
    off = (np.arange(sub) + 0.5) / sub * IMERG_STEP - half
    cells, total = [], 0
    for i in range(i_lo, i_hi + 1):
        for j in range(j_lo, j_hi + 1):
            clon, clat = IMERG_LON0 + i * IMERG_STEP, IMERG_LAT0 + j * IMERG_STEP
            gx, gy = np.meshgrid(clon + off, clat + off)
            k = int(_in_polygons(gx.ravel(), gy.ravel(), polys).sum())
            if k:
                cells.append({"i": i, "j": j, "lon": round(clon, 4), "lat": round(clat, 4), "k": k})
                total += k
    if not cells:   # polígono menor que el muestreo: celda que contiene el centroide
        cx, cy = (w + e) / 2, (s + n) / 2
        i = int(round((cx - IMERG_LON0) / IMERG_STEP)); j = int(round((cy - IMERG_LAT0) / IMERG_STEP))
        return [{"i": i, "j": j, "lon": round(IMERG_LON0 + i * IMERG_STEP, 4),
                 "lat": round(IMERG_LAT0 + j * IMERG_STEP, 4), "weight": 1.0}]
    for c in cells:
        c["weight"] = c.pop("k") / total
    return cells


def imerg_zone_value(win: np.ndarray, cells: list[dict], i0: int, j0: int) -> tuple[float, int]:
    """Valor zonal de un día. win = ventana (lon, lat) que empieza en (i0, j0).
    Relleno o negativo -> NaN; si falta CUALQUIER celda, el día queda NaN (la lluvia
    nunca se rellena ni se interpola). Devuelve (mm/día, celdas válidas)."""
    vals = np.array([win[c["i"] - i0, c["j"] - j0] for c in cells], float)
    vals[(vals <= IMERG_FILL_LIMIT) | (vals < 0)] = np.nan
    n_ok = int(np.isfinite(vals).sum())
    if n_ok < len(vals):
        return float("nan"), n_ok
    return float(np.dot(vals, [c["weight"] for c in cells])), n_ok


def _imerg_read_granule(g, i0, i1, j0, j1, retries: int = 3):
    """Lee solo la ventana de celdas necesaria (recorte en origen si el servidor
    permite lecturas parciales). Devuelve (ventana lon x lat, 'YYYY-MM-DD', chunksizes)."""
    import earthaccess
    import xarray as xr
    last = None
    for a in range(retries):
        try:
            f = earthaccess.open([g])[0]
            with xr.open_dataset(f, engine="h5netcdf") as ds:
                v = ds[IMERG_VAR]
                lon_i0 = float(ds["lon"].values[i0])
                lat_j0 = float(ds["lat"].values[j0])
                if abs(lon_i0 - (IMERG_LON0 + i0 * IMERG_STEP)) > 1e-3 or \
                   abs(lat_j0 - (IMERG_LAT0 + j0 * IMERG_STEP)) > 1e-3:
                    raise RuntimeError("la rejilla del archivo no coincide con la esperada (índices)")
                win = np.asarray(v.isel(time=0, lon=slice(i0, i1 + 1), lat=slice(j0, j1 + 1)).values, float)
                day = str(ds["time"].values[0])[:10]
                return win, day, v.encoding.get("chunksizes")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** a)
    raise RuntimeError(f"no se pudo leer el granulo: {last}")


def fetch_imerg(zone: str, geojson: str, start: str, end: str,
                workers: int = 4, force: bool = False) -> dict:
    """IMERG Final V07 diario -> serie zonal (media ponderada por área de celdas de 0.1°).
    Una ingesta por año (raw inmutable + manifiesto); un año ya ingerido se omite salvo --force.
    El raw es la ventana de celdas por día (no el archivo global de ~28 MB)."""
    import earthaccess
    from concurrent.futures import ThreadPoolExecutor
    if not (os.environ.get("EARTHDATA_TOKEN") or
            (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))):
        raise RuntimeError("Falta EARTHDATA_TOKEN (o EARTHDATA_USERNAME/EARTHDATA_PASSWORD) en el entorno")
    earthaccess.login(strategy="environment")

    cells = imerg_cells(read_polygons(geojson))
    i0, i1 = min(c["i"] for c in cells), max(c["i"] for c in cells)
    j0, j1 = min(c["j"] for c in cells), max(c["j"] for c in cells)
    cell_sig = [(c["lon"], c["lat"], round(c["weight"], 6)) for c in cells]
    print(f"Celdas IMERG de la zona: {len(cells)}  (pesos por área, suma 1)")

    done = {(e["params"].get("zone"), e["params"].get("start"), e["params"].get("end"),
            json.dumps(e["params"].get("cells"))) for e in read_manifest()
            if e["source"] == "IMERG_FINAL" and e["status"] == "ok"}
    summary = {"zone": zone, "years": {}}
    for year in range(int(start[:4]), int(end[:4]) + 1):
        ys, ye = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        key = (zone, ys, ye, json.dumps(cell_sig))
        if key in done and not force:
            print(f"{year}: ya ingerido (omitido; use --force para repetir)")
            summary["years"][year] = "omitido"
            continue
        t0 = time.time()
        granules = earthaccess.search_data(short_name=IMERG_SHORT_NAME, version=IMERG_VERSION,
                                            temporal=(ys, ye))
        print(f"{year}: {len(granules)} archivos encontrados ({ys} a {ye})")

        def work(g):
            win, day, chunks = _imerg_read_granule(g, i0, i1, j0, j1)
            val, n_ok = imerg_zone_value(win, cells, i0, j0)
            name = Path(g.data_links()[0]).name
            return {"date": day, "precip_mm": val, "n_valid_cells": n_ok, "granule": name}, chunks

        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            res = list(ex.map(work, granules))
        rows = sorted((r for r, _ in res), key=lambda r: r["date"])
        chunks = next((c for _, c in res if c), None)
        full = pd.date_range(ys, ye, freq="D")
        have = {r["date"] for r in rows}
        missing = [d.strftime("%Y-%m-%d") for d in full if d.strftime("%Y-%m-%d") not in have]
        raw = {"label": "IMERG Final V07 diario, ventana de celdas de la zona",
                "cells": cells, "rows": [{**r, "precip_mm": None if math.isnan(r["precip_mm"]) else r["precip_mm"]}
                                        for r in rows]}
        digest, path = save_raw("imerg", json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        n_nan = sum(1 for r in rows if math.isnan(r["precip_mm"]))
        log_ingestion(source="IMERG_FINAL", product=IMERG_SHORT_NAME, version=IMERG_VERSION,
                        params={"zone": zone, "start": ys, "end": ye, "cells": cell_sig, "var": IMERG_VAR},
                        raw_uri=path, raw_sha256=digest, n_records=len(rows), status="ok",
                        report={"missing_days": missing[:50], "n_missing_days": len(missing),
                                "n_days_nan": n_nan, "chunksizes": str(chunks),
                                "elapsed_s": round(time.time() - t0, 1), "workers": workers})
        df = pd.DataFrame(rows).set_index(pd.to_datetime([r["date"] for r in rows]))
        df = df.reindex(full)
        df.index.name = "obs_date"
        clean = pd.DataFrame({"precip_mm": df.precip_mm, "n_valid_cells": df.n_valid_cells})
        write_table(clean, DATA_DIR / "clean" / "imerg" / zone / str(year))
        summary["years"][year] = {"dias": len(rows), "faltan": len(missing), "nan": n_nan,
                                    "segundos": round(time.time() - t0, 1), "chunksizes": str(chunks)}
        print(f"{year}: {summary['years'][year]}")
    return summary


def read_imerg_clean(zone: str) -> pd.Series | None:
    d = DATA_DIR / "clean" / "imerg" / zone
    if not d.exists():
        return None
    parts = [read_table(d / s) for s in sorted({p.stem for p in d.glob("*.*")})]
    if not parts:
        return None
    df = pd.concat(parts).sort_index()
    df.index = pd.to_datetime(df.index)
    return df["precip_mm"]


def compare_precip(imerg: pd.Series, power: pd.Series) -> dict:
    """IMERG vs POWER: diario, mensual (meses completos) y anual (años completos).
    Sesgos = IMERG - POWER. No imputa nada."""
    j = pd.concat(
        [imerg, power],
        axis=1,
        keys=["imerg", "power"],
        sort=False
    ).dropna()
    out: dict = {"n_days_common": int(len(j))}
    if len(j) < 30:
        out["note"] = "menos de 30 días en común; sin comparación"
        return out
    d = j.imerg - j.power
    out["daily"] = {"corr": round(float(j.corr().iloc[0, 1]), 3),
                    "bias_mm_day": round(float(d.mean()), 3),
                    "rmse_mm_day": round(float(np.sqrt((d ** 2).mean())), 3)}
    g = j.groupby([j.index.year, j.index.month])
    cnt = g.size()
    dim = pd.Series([pd.Period(f"{y}-{m:02d}").days_in_month for y, m in cnt.index], index=cnt.index)
    msum = g.sum()[cnt == dim]
    if len(msum) >= 6:
        out["monthly"] = {"n_months": int(len(msum)),
                            "corr": round(float(msum.corr().iloc[0, 1]), 3),
                            "ratio_imerg_over_power": round(float(msum.imerg.sum() / msum.power.sum()), 3)}
    gy = j.groupby(j.index.year)
    cy = gy.size()
    dy = pd.Series([366 if pd.Timestamp(f"{y}-12-31").day_of_year == 366 else 365 for y in cy.index], index=cy.index)
    ysum = gy.sum()[cy == dy]
    if len(ysum):
        out["annual_mm"] = {int(y): {"imerg": round(float(r.imerg), 0), "power": round(float(r.power), 0),
                                        "ratio": round(float(r.imerg / r.power), 3) if r.power else None}
                            for y, r in ysum.iterrows()}
    out["note"] = ("el día IMERG es UTC; la hora local de Guatemala es UTC-6. La comparación diaria "
                    "tiene desfase parcial; confiar más en la mensual y la anual [Verificar]")
    return out


# ----------------------------------------------------------------------------
# 3. Limpieza (capa clean)
# ----------------------------------------------------------------------------
def extraterrestrial_radiation(doy: np.ndarray, lat_deg: float) -> np.ndarray:
    """Ra en MJ m-2 día-1 (FAO-56 ec. 21)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-math.tan(phi) * np.tan(delta), -1, 1))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws))


def _power_units(data: dict) -> dict:
    """Unidades leídas del encabezado de la respuesta, no supuestas."""
    out = {}
    for k, v in (data.get("parameters") or {}).items():
        if isinstance(v, dict):
            out[k] = v.get("units", "")
    return out


def power_to_frame(data: dict) -> tuple[pd.DataFrame, dict]:
    """JSON de POWER -> DataFrame con nombres/unidades del proyecto + notas."""
    notes = {"unit_warnings": []}
    units = _power_units(data)
    df = pd.DataFrame(data["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "obs_date"
    df = df.sort_index()
    # Radiación: convertir a MJ/m2/día solo según la unidad declarada.
    u = units.get("ALLSKY_SFC_SW_DWN", "")
    miss = df == -999
    if "kw" in u.lower() and "hr" in u.lower():
        df["ALLSKY_SFC_SW_DWN"] = df["ALLSKY_SFC_SW_DWN"] * 3.6
    elif "mj" not in u.lower():
        notes["unit_warnings"].append(
            f"unidad de radiación no reconocida ({u!r}); se asume MJ/m2/día [Verificar]")
    df = df.rename(columns=RENAME)
    miss = miss.rename(columns=RENAME)
    df = df.mask(miss | df.eq(-999))
    return df, notes


def _fill_short_gaps(s: pd.Series, max_gap: int) -> tuple[pd.Series, pd.Series]:
    """Interpolación lineal SOLO de huecos de hasta `max_gap` días consecutivos."""
    isna = s.isna()
    run_id = (isna != isna.shift()).cumsum()
    run_len = isna.groupby(run_id).transform("sum")
    fillable = isna & (run_len <= max_gap)
    interp = s.interpolate(method="linear", limit_area="inside")
    out = s.copy()
    out[fillable] = interp[fillable]
    filled = fillable & out.notna()
    return out, filled


def clean_climate(df_raw: pd.DataFrame, lat: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """QC físico + banderas + relleno de huecos cortos (nunca lluvia).
    Devuelve (serie limpia, copia previa al relleno para la cobertura)."""
    df = df_raw.copy()
    flags = pd.Series(0, index=df.index, dtype="int32")

    # bit 1: cualquier variable ausente en el día (antes de cualquier relleno)
    flags |= df.isna().any(axis=1).astype("int32") * F_MISSING

    # bit 2: fuera de rango (se anula SOLO la variable afectada)
    def bad(mask: pd.Series, cols: list[str]):
        nonlocal flags
        mask = mask.fillna(False)
        flags |= mask.astype("int32") * F_RANGE
        df.loc[mask, cols] = np.nan

    bad((df.tmax_c < -60) | (df.tmax_c > 60), ["tmax_c"])
    bad((df.tmin_c < -60) | (df.tmin_c > 60), ["tmin_c"])
    bad(df.tmax_c < df.tmin_c, ["tmax_c", "tmin_c"])
    bad((df.rh_pct < 0) | (df.rh_pct > 100), ["rh_pct"])
    bad(df.wind2m_ms < 0, ["wind2m_ms"])
    bad(df.precip_mm < 0, ["precip_mm"])
    tmean = (df.tmax_c + df.tmin_c) / 2
    bad(df.tdew_c > tmean + TDEW_TOL_C, ["tdew_c"])  # ese día se usa la ruta RH2M
    ra = pd.Series(extraterrestrial_radiation(df.index.day_of_year.values, lat), index=df.index)
    bad((df.srad_mj_m2 < 0) | (df.srad_mj_m2 > ra), ["srad_mj_m2"])

    df_prefill = df.copy()  # para cobertura honesta

    # bit 4: relleno lineal de huecos <= 3 días; la lluvia NUNCA se interpola
    for v in MET_VARS:
        df[v], filled = _fill_short_gaps(df[v], MAX_GAP_FILL_DAYS)
        flags |= filled.astype("int32") * F_GAPFILL

    # bit 16: radiación modelada con Hargreaves-Samani si aún falta (evidencia C)
    need = df.srad_mj_m2.isna() & df.tmax_c.notna() & df.tmin_c.notna()
    hs = HS_KRS * np.sqrt((df.tmax_c - df.tmin_c).clip(lower=0)) * ra
    df.loc[need, "srad_mj_m2"] = hs[need]
    flags |= need.astype("int32") * F_RAD_MODEL

    df["qc_flags"] = flags
    return df, df_prefill


# ----------------------------------------------------------------------------
# 4. Curación: ET0, Pef, decenas, cobertura
# ----------------------------------------------------------------------------
def e0(t):
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def et0_fao56(df: pd.DataFrame, lat: float, elev_m: float,
            ea_override: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """ET0 FAO-56 Penman-Monteith diario (G=0). Devuelve (et0, ea_method).
    ea: ruta R1 (punto de rocío) si hay tdew; si no, R2 (RH2M). Etiqueta por día."""
    tmax, tmin = df.tmax_c.values, df.tmin_c.values
    tmean = (tmax + tmin) / 2
    u2, rs = df.wind2m_ms.values, df.srad_mj_m2.values
    doy = df.index.day_of_year.values
    P = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26   # presión con el DEM
    gamma = 0.665e-3 * P
    es = (e0(tmax) + e0(tmin)) / 2
    delta = 4098 * e0(tmean) / (tmean + 237.3) ** 2
    if ea_override is not None:
        ea, method = ea_override, np.array(["override"] * len(df))
    else:
        r1 = e0(df.tdew_c.values)
        r2 = df.rh_pct.values / 100 * es
        use_r1 = ~np.isnan(r1)
        ea = np.where(use_r1, r1, r2)
        method = np.where(use_r1, "R1_dewpoint", np.where(~np.isnan(r2), "R2_rh", "none"))
    ea = np.minimum(ea, es)
    ra = extraterrestrial_radiation(doy, lat)
    rso = (0.75 + 2e-5 * elev_m) * ra
    ratio = np.clip(np.divide(rs, rso, out=np.full_like(rs, np.nan, dtype=float), where=rso > 0), None, 1.0)
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 \
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0))) * (1.35 * ratio - 0.35)
    rn = 0.77 * rs - rnl
    num = 0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (es - ea)
    et0 = num / (delta + gamma * (1 + 0.34 * u2))
    return np.maximum(et0, 0.0), method   # acotado a >= 0


def dekad_of_day(idx: pd.DatetimeIndex) -> np.ndarray:
    d = idx.day
    inner = np.where(d <= 10, 1, np.where(d <= 20, 2, 3))
    return (idx.month - 1) * 3 + inner      # 1..36


def peff_month(p: np.ndarray, method: str, phi: float | None = None) -> np.ndarray:
    """Pef mensual (mm/mes). Formulas USDA-SCS/FAO [Verificar] (DP-06)."""
    p = np.asarray(p, dtype=float)
    if method == "usda_scs_fao":
        return np.where(p <= 250, p * (125 - 0.2 * p) / 125, 125 + 0.1 * p)
    if method == "fao_dependable":
        return np.where(p <= 70, np.maximum(0, 0.6 * p - 10), 0.8 * p - 24)
    raise ValueError(method)


def build_dekad(daily: pd.DataFrame, phi: float | None = None) -> pd.DataFrame:
    """Agregados por decena con Pef de los cuatro métodos habilitados.
    Los métodos mensuales devuelven NaN si algún día de precipitación del mes falta."""
    d = daily.copy()
    d["year"] = d.index.year
    d["month"] = d.index.month
    d["dekad"] = dekad_of_day(d.index)
    p_nan = d.precip_mm.isna()
    g = d.groupby(["year", "dekad"])
    out = pd.DataFrame({
        "p_mm": g.precip_mm.sum(min_count=1),
        "et0_mm": g.et0_mm.sum(min_count=1),
        "n_days": g.precip_mm.size(),
        "n_valid_days": g.precip_mm.count(),
    })
    out["month"] = g.month.first()
    # Pef mensual
    gm = d.groupby(["year", "month"])
    p_month = gm.precip_mm.sum(min_count=1)
    month_has_gap = p_nan.groupby([d.year, d.month]).any()
    for m in ("usda_scs_fao", "fao_dependable"):
        pm = pd.Series(peff_month(p_month.fillna(0).values, m), index=p_month.index)
        pm[month_has_gap.reindex(pm.index).values] = np.nan
        key = pd.MultiIndex.from_arrays([out.index.get_level_values(0), out["month"]])
        pm_for = pm.reindex(key).values
        pmo = p_month.reindex(key).values
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(pmo > 0, out.p_mm.values / pmo, 0.0)   # Pef_d = Pef_mes * P_d / P_mes
        out[f"pef_mm_{m}"] = pm_for * share
    gap_dek = g.precip_mm.apply(lambda s: s.isna().any())
    out["pef_mm_upper_bound"] = out.p_mm.where(~gap_dek)
    out["pef_mm_fixed_fraction"] = (phi * out.p_mm).where(~gap_dek) if phi is not None else np.nan
    out["pef_month_total_usda_scs_fao"] = pd.Series(
        peff_month(p_month.fillna(0).values, "usda_scs_fao"), index=p_month.index
    ).where(~month_has_gap.reindex(p_month.index)).reindex(
        pd.MultiIndex.from_arrays([out.index.get_level_values(0), out["month"]])).values
    return out.drop(columns=["month"]).reset_index()


def build_coverage(prefill: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for var in ["precip_mm"] + MET_VARS:
        g = prefill[var].groupby(prefill.index.year)
        n_exp, n_val = g.size(), g.count()
        for y in n_exp.index:
            rows.append({"variable": var, "year": int(y), "n_expected": int(n_exp[y]),
                        "n_valid": int(n_val[y]),
                        "pct_missing": round(100 * (1 - n_val[y] / n_exp[y]), 3)})
    return pd.DataFrame(rows)


def validate_series(df: pd.DataFrame, start: str, end: str):
    errs = []
    full = pd.date_range(start, end, freq="D")
    if df.index.duplicated().any():
        errs.append("fechas duplicadas")
    missing = full.difference(df.index)
    if len(missing):
        errs.append(f"faltan {len(missing)} fechas en la serie (p. ej. {missing[0].date()})")
    if errs:
        raise ValidationFailed("; ".join(errs))


def curate_zone(zone: str, lat: float, lon: float, elev_m: float,
                start="2001-01-01", end="2025-12-31", phi: float | None = None,
                force: bool = False) -> dict:
    """POWER raw -> clean (por año) -> curated. Idempotente por hash de entrada."""
    entries = [e for e in read_manifest()
                if e["source"] == "POWER_DAILY" and e["params"].get("zone") == zone and e["status"] == "ok"]
    if not entries:
        raise ValidationFailed(f"no hay ingesta POWER ok para la zona {zone}; ejecute fetch-power")
    raw_hashes = sorted({e["raw_sha256"] for e in entries[-1:]})
    last = entries[-1]
    data = json.loads(Path(last["raw_uri"]).read_text(encoding="utf-8"))
    return curate_from_power_json(zone, data, raw_hashes, lat, elev_m, start, end, phi, force)


def curate_from_power_json(zone, data, raw_hashes, lat, elev_m,
                        start="2001-01-01", end="2025-12-31", phi=None, force=False) -> dict:
    cur_dir = DATA_DIR / "curated" / zone
    meta_p = cur_dir / "curated_meta.json"
    in_hash = sha256_bytes((",".join(raw_hashes) + f"|{lat}|{elev_m}|{start}|{end}|{phi}").encode())
    if meta_p.exists() and not force:
        old = json.loads(meta_p.read_text())
        if old.get("input_hash") == in_hash:
            return {**old, "skipped": True}           # idempotente
    raw, notes = power_to_frame(data)
    try:
        validate_series(raw, start, end)
    except ValidationFailed as e:
        log_ingestion(source="CURATE", product="curate", version=None, params={"zone": zone},
                        raw_uri="", raw_sha256="", n_records=0, status="failed",
                        report={"error": str(e)})
        raise                                   # nada se escribe en curated
    daily, prefill = clean_climate(raw, lat)
    # clean: una partición por año
    for y, part in daily.groupby(daily.index.year):
        write_table(part, DATA_DIR / "clean" / "power" / zone / str(y))
    # ET0 (se prefiere milpa_core si está disponible)
    try:
        from milpa_core.climate import et0_fao56 as core_et0  # type: ignore
        et0, method = core_et0(daily, lat, elev_m)
        et0_src = "milpa_core.climate"
    except Exception:  # noqa: BLE001
        et0, method = et0_fao56(daily, lat, elev_m)
        et0_src = "milpa_r1.et0_fao56 (respaldo local; confirmar con R2)"
    daily["et0_mm"], daily["ea_method"] = et0, method
    daily["precip_source"] = "POWER_PRECTOTCORR"   # sin IMERG todavía
    dekad = build_dekad(daily, phi)
    cov = build_coverage(prefill)
    write_table(daily, cur_dir / "daily")
    write_table(dekad, cur_dir / "dekad")
    write_table(cov, cur_dir / "coverage")
    data_hash = sha256_bytes((",".join(raw_hashes) + logical_hash(daily)).encode())
    meta = {"zone": zone, "input_hash": in_hash, "data_hash": data_hash,
            "raw_sha256": raw_hashes, "et0_source": et0_src, "n_days": int(len(daily)),
            "parquet": HAS_PARQUET, "notes": notes,
            "limitations": ["lluvia = POWER PRECTOTCORR (IMERG pendiente)",
                            "unidad de día POWER vs UTC-6 [Verificar]"]}
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


# ----------------------------------------------------------------------------
# 5. Validación cruzada
# ----------------------------------------------------------------------------
def validate_zone(zone: str, lat: float, elev_m: float, station_csv: str | None = None) -> dict:
    daily = read_table(DATA_DIR / "curated" / zone / "daily")
    daily.index = pd.to_datetime(daily.index)
    et_r1, _ = et0_fao56(daily.assign(rh_pct=daily.rh_pct), lat, elev_m)
    d2 = daily.copy()
    d2["tdew_c"] = np.nan                      # fuerza la ruta R2 (RH2M)
    et_r2, _ = et0_fao56(d2, lat, elev_m)
    s1, s2 = pd.Series(et_r1, index=daily.index), pd.Series(et_r2, index=daily.index)
    diff = (s1 - s2)
    season = diff.groupby(diff.index.month).mean().round(3).to_dict()
    report = {"et0_T2MDEW_vs_RH2M": {
        "mean_abs_diff_mm_day": round(float(diff.abs().mean()), 4),
        "mean_diff_by_month": {int(k): v for k, v in season.items()},
        "note": "si supera region.et0.ea_sensitivity_tol [Pendiente] -> limitación ea_sensible_a_la_ruta"}}
    if station_csv:
        st = pd.read_csv(station_csv, parse_dates=["date"]).set_index("date")
        j = pd.concat([daily.precip_mm, st.precip_mm], axis=1, keys=["power", "station"]).dropna()
        if len(j) > 10:
            report["precip_POWER_vs_station"] = {
                "n": int(len(j)), "corr": round(float(j.corr().iloc[0, 1]), 3),
                "bias_mm_day": round(float((j.power - j.station).mean()), 3)}
    im = read_imerg_clean(zone)
    if im is not None:
        report["precip_IMERG_vs_POWER"] = compare_precip(im, daily.precip_mm)
    else:
        report["precip_IMERG_vs_POWER"] = "pendiente: ejecute fetch-imerg para esta zona"
    out = DATA_DIR / "curated" / zone / "validation_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


# ----------------------------------------------------------------------------
# 6. CSV de suelo por propiedad (apartado 9 y 13.4)
# ----------------------------------------------------------------------------
SOIL_PROPS = {  # propiedad: (columna de valor, columna de método, mín, máx, unidad)
    "ph": ("ph", "ph_method", 3.0, 10.0, "pH"),
    "organic_matter": ("om_pct", "om_method", 0, 100, "%"),
    "cec": ("cec_cmol_kg", "cec_method", 0, 200, "cmol/kg"),
    "effective_depth": ("effective_root_depth_cm", None, 0, 1000, "cm"),
    "awc": ("awc_mm_per_m", "awc_method", 0, 400, "mm/m"),
}


def ingest_soil_csv(parcel: str, path: str) -> dict:
    """Valida y descompone un CSV ancho en filas por propiedad.
    Celda vacía = no medido (no hay fila). Cada valor exige su método."""
    raw_bytes = Path(path).read_bytes()
    digest, raw_path = save_raw("soil_csv", raw_bytes)
    df = pd.read_csv(path, encoding="utf-8")
    errors, rows = [], []
    for i, r in df.iterrows():
        ln = i + 2
        if str(r.get("parcel_code")) != parcel:
            errors.append(f"fila {ln}: parcel_code no coincide con {parcel}")
        try:
            sd = pd.to_datetime(r["sample_date"]).date()
            if sd > date.today():
                errors.append(f"fila {ln}: fecha futura")
        except Exception:  # noqa: BLE001
            errors.append(f"fila {ln}: fecha inválida"); sd = None
        if not (pd.notna(r.get("depth_from_cm")) and pd.notna(r.get("depth_to_cm"))
                and r["depth_to_cm"] > r["depth_from_cm"]):
            errors.append(f"fila {ln}: profundidades inválidas")
        for prop, (vc, mc, lo, hi, unit) in SOIL_PROPS.items():
            v = r.get(vc)
            if pd.isna(v):
                continue
            if not (lo <= v <= hi):
                errors.append(f"fila {ln}: {vc}={v} fuera de [{lo}, {hi}]")
            method = r.get(mc) if mc else "declarado/medido"
            if mc and (pd.isna(method) or str(method).strip() == ""):
                errors.append(f"fila {ln}: {vc} requiere {mc}")
            rows.append({"parcel_code": parcel, "sample_date": sd, "property_code": prop,
                        "value": float(v), "unit": unit, "method": method,
                        "depth_from_cm": r.get("depth_from_cm"), "depth_to_cm": r.get("depth_to_cm")})
        tex = [r.get("sand_pct"), r.get("silt_pct"), r.get("clay_pct")]
        if any(pd.notna(t) for t in tex):
            if not all(pd.notna(t) for t in tex):
                errors.append(f"fila {ln}: textura incompleta (arena, limo y arcilla)")
            elif abs(sum(tex) - 100) > 2:
                errors.append(f"fila {ln}: arena+limo+arcilla = {sum(tex)} (debe ser 100 ± 2)")
            elif pd.isna(r.get("texture_method")):
                errors.append(f"fila {ln}: textura requiere texture_method")
            else:
                for pc, val in zip(("sand", "silt", "clay"), tex):
                    rows.append({"parcel_code": parcel, "sample_date": sd, "property_code": pc,
                                "value": float(val), "unit": "%", "method": r["texture_method"],
                                "depth_from_cm": r.get("depth_from_cm"), "depth_to_cm": r.get("depth_to_cm")})
    status = "failed" if errors else "ok"
    log_ingestion(source="LAB_CSV", product="soil csv", version=None, params={"parcel": parcel},
                raw_uri=raw_path, raw_sha256=digest, n_records=len(rows), status=status,
                report={"errors": errors} if errors else None)
    if errors:
        return {"status": "failed", "errors": errors}
    long = pd.DataFrame(rows)
    write_table(long.set_index("property_code"), DATA_DIR / "curated" / "soil" / parcel)
    measured = sorted(long.property_code.unique())
    unknown = [p for p in list(SOIL_PROPS) + ["sand", "silt", "clay"] if p not in measured]
    return {"status": "ok", "measured": measured, "unknown": unknown}


# ----------------------------------------------------------------------------
# 7. Validador de catálogos y region pack (apartado 11.14)
# ----------------------------------------------------------------------------
def find_pending(node, path="") -> list[str]:
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            found += find_pending(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += find_pending(v, f"{path}[{i}]")
    elif isinstance(node, str) and node.strip().lower() == "pending":
        found.append(path)
    return found


def validate_catalog(file: str, mode: str | None = None) -> dict:
    """En production: cualquier `pending` o un umbral sin cita hace fallar.
    En sandbox: corre y avisa; todo lo afectado queda 'provisional'."""
    mode = mode or MILPA_MODE
    if yaml is None:
        raise RuntimeError("Falta pyyaml")
    doc = yaml.safe_load(Path(file).read_text(encoding="utf-8"))
    pend = find_pending(doc)
    problems = []

    def walk(n):
        if isinstance(n, dict):
            if "metric" in n or "risk_thresholds" in n:           # umbral
                if "metric" in n and not n.get("citation"):
                    problems.append("umbral sin cita")
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(doc)
    ok = not problems and not (mode == "production" and pend)
    result = {"file": file, "mode": mode, "ok": ok, "n_pending": len(pend),
            "pending": pend[:50], "problems": problems,
            "label": None if mode == "production" else "umbral provisional — no usar para decisión"}
    if mode == "production" and not ok:
        raise ValidationFailed(f"{file}: {len(pend)} campos pending / {problems}")
    return result


# ----------------------------------------------------------------------------
# 8. Demostración sintética congelada + privacidad
# ----------------------------------------------------------------------------
def synthetic_power_json(seed: int = 0, lat: float = 14.8, start="2001-01-01", end="2025-12-31") -> dict:
    """Respuesta tipo POWER con datos SINTÉTICOS (rotulados). Incluye centinelas -999
    y huecos para ejercitar el mismo camino que los datos reales."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="D")
    doy = idx.day_of_year.values
    tmean = 24 + 3 * np.sin(2 * np.pi * (doy - 100) / 365) + rng.normal(0, 0.8, len(idx))
    rng_t = 9 + rng.normal(0, 0.6, len(idx))
    tmax, tmin = tmean + rng_t / 2, tmean - rng_t / 2
    wet = (doy > 135) & (doy < 300)
    rain = np.where(rng.random(len(idx)) < np.where(wet, 0.45, 0.05),
                    rng.gamma(1.4, 9, len(idx)), 0.0)
    rh = np.clip(55 + 25 * wet + rng.normal(0, 6, len(idx)), 20, 99)
    tdew = tmean - (100 - rh) / 5
    wind = np.clip(rng.normal(1.6, 0.5, len(idx)), 0.3, None)
    ra = extraterrestrial_radiation(doy, lat)
    srad = np.clip(ra * (0.65 - 0.25 * (rain > 0)) * 0.95, 4, None)
    vals = {"T2M_MAX": tmax, "T2M_MIN": tmin, "T2MDEW": tdew, "RH2M": rh, "WS2M": wind,
            "ALLSKY_SFC_SW_DWN": srad, "PRECTOTCORR": rain}
    param = {}
    for k, v in vals.items():
        v = np.round(v, 2)
        v[rng.choice(len(v), 40, replace=False)] = -999          # centinelas
        param[k] = {d.strftime("%Y%m%d"): float(x) for d, x in zip(idx, v)}
    return {"label": "DATOS SINTÉTICOS — no representan ninguna zona real",
            "parameters": {k: {"units": ("MJ/m^2/day" if k == "ALLSKY_SFC_SW_DWN" else "x")} for k in vals},
            "properties": {"parameter": param}}


COORD_RE = re.compile(r"(?<![\d.])-?\d{1,3}\.\d{4,}(?![\d.])")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def scan_privacy(root: Path) -> list[str]:
    """Falla si hay coordenadas con más de 3 decimales o correos (apartado 22).
    Nota: puede dar falsos positivos en columnas numéricas con muchos decimales;
    por eso las tablas se escriben con float_format de 6 decimales solo para hashes,
    y esta prueba excluye los archivos de series (se revisan manifest y JSON)."""
    hits = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in {".json", ".jsonl", ".yaml", ".yml", ".md", ".txt"}:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if EMAIL_RE.search(txt):
                hits.append(f"{p}: correo")
            if COORD_RE.search(txt) and p.name != "EXPECTED.json":
                hits.append(f"{p}: coordenada con >3 decimales")
    return hits


def build_demo(zone="zona_sintetica", seed=0) -> dict:
    """Congela data/demo/ con serie curada sintética, manifiesto SHA-256 y EXPECTED.json."""
    global DATA_DIR
    real_dir = DATA_DIR
    DATA_DIR = real_dir / "_demo_work"
    try:
        data = synthetic_power_json(seed)
        raw_bytes = json.dumps(data, sort_keys=True).encode()
        digest, rp = save_raw("power", raw_bytes)
        log_ingestion(source="POWER_DAILY", product="SINTETICO", version="synthetic-v1",
                    params={"zone": zone, "seed": seed}, raw_uri=rp, raw_sha256=digest,
                    n_records=len(data["properties"]["parameter"]["T2M_MAX"]), status="ok")
        meta = curate_from_power_json(zone, data, [digest], lat=14.8, elev_m=500.0, phi=None, force=True)
        demo = real_dir / "demo"
        demo.mkdir(parents=True, exist_ok=True)
        files = {}
        for f in sorted((DATA_DIR / "curated" / zone).glob("*")):
            dst = demo / zone / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())
            files[f"{zone}/{f.name}"] = sha256_file(dst)
        (demo / "LEEME.txt").write_text(
            "Datos SINTÉTICOS rotulados: fixture de prueba, no representa un suelo ni un clima reales.\n"
            "Sin coordenadas de parcelas ni datos personales.\n", encoding="utf-8")
        expected = {"zone": zone, "seed": seed, "data_hash": meta["data_hash"],
                    "label": "datos sintéticos", "files_sha256": files,
                    "parquet": HAS_PARQUET}
        (demo / "EXPECTED.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
        return expected
    finally:
        DATA_DIR = real_dir


# ----------------------------------------------------------------------------
# Autoprueba (sin red)
# ----------------------------------------------------------------------------
def selftest() -> int:
    import tempfile
    global DATA_DIR
    results = []

    def check(name, cond, extra=""):
        results.append((name, bool(cond), extra))

    # ET0: ejemplo FAO-56 (Ej. 18, Uccle 6 jul; ea=1.409, Rs=22.07, u2=2.078, z=100, lat 50.8)
    df = pd.DataFrame({"tmax_c": [21.5], "tmin_c": [12.3], "tdew_c": [np.nan], "rh_pct": [np.nan],
                    "wind2m_ms": [2.078], "srad_mj_m2": [22.07]},
                    index=pd.to_datetime(["2001-07-06"]))
    et, _ = et0_fao56(df, 50.8, 100.0, ea_override=np.array([1.409]))
    check("ET0 FAO-56 Ejemplo 18 ≈ 3.9 mm/día (tol 0.15)", abs(et[0] - 3.9) < 0.15, f"obtenido {et[0]:.3f}")

    # Relleno de huecos y lluvia
    idx = pd.date_range("2001-01-01", periods=20)
    t = pd.Series(np.arange(20, dtype=float), index=idx)
    t.iloc[3:6] = np.nan      # hueco de 3 -> se rellena
    t.iloc[10:14] = np.nan    # hueco de 4 -> NO se rellena
    f, filled = _fill_short_gaps(t, 3)
    check("relleno de hueco de 3 días", f.iloc[3:6].notna().all() and filled.iloc[3:6].all())
    check("hueco de 4 días queda sin rellenar", f.iloc[10:14].isna().all())

    # Pef: propiedades
    P = np.linspace(0, 600, 61)
    for m in ("usda_scs_fao", "fao_dependable"):
        pe = peff_month(P, m)
        check(f"Pef {m}: 0 ≤ Pef ≤ P", np.all(pe >= -1e-9) and np.all(pe <= P + 1e-9))
        check(f"Pef {m}: no decrece con P", np.all(np.diff(pe) >= -1e-9))
    check("Pef(0)=0", peff_month(np.array([0.0]), "usda_scs_fao")[0] == 0)

    with tempfile.TemporaryDirectory() as td:
        DATA_DIR = Path(td) / "data"
        a = build_demo(seed=0)
        b_dir = Path(td) / "data2"
        DATA_DIR = b_dir
        b = build_demo(seed=0)
        DATA_DIR = Path(td) / "data"
        check("determinismo: mismo data_hash en dos corridas", a["data_hash"] == b["data_hash"])
        zone = "zona_sintetica"
        daily = read_table(DATA_DIR / "demo" / zone / "daily")
        daily.index = pd.to_datetime(daily.index)
        check("serie diaria completa 2001-2025", len(daily) == 9131, f"{len(daily)} días")
        _c, _p = clean_climate(power_to_frame(synthetic_power_json(1, end="2001-12-31"))[0], 14.8)
        check("sin objetos en DataFrame.attrs (Parquet no los serializa)", _c.attrs == {} and _p.attrs == {})
        try:
            json.dumps(_c.attrs)
            _attrs_ok = True
        except TypeError:
            _attrs_ok = False
        check("attrs serializable a JSON", _attrs_ok)
        check("lluvia faltante nunca es cero (NaN conservado)",
                daily.precip_mm.isna().sum() > 0 and (daily.loc[daily.precip_mm.isna(), "qc_flags"] & 1 > 0).all())
        check("bit 1 presente en días con faltantes", (daily.qc_flags & 1 > 0).any())
        check("ET0 ≥ 0 y finito donde hay insumos", (daily.et0_mm.dropna() >= 0).all())
        check("ea_method registrado por día", daily.ea_method.isin(["R1_dewpoint", "R2_rh", "none"]).all())
        dek = read_table(DATA_DIR / "demo" / zone / "dekad")
        check("36 decenas por año", dek.groupby("year").size().eq(36).all()
                if "year" in dek.columns else True)
        ok_pef = dek.pef_mm_usda_scs_fao.dropna()
        check("Pef decenal ≤ P decenal", (ok_pef <= dek.loc[ok_pef.index, "p_mm"] + 1e-6).all())
        # suma de decenas = Pef del mes
        dd = dek.dropna(subset=["pef_mm_usda_scs_fao", "pef_month_total_usda_scs_fao"]).copy()
        dd["month"] = ((dd["dekad"] - 1) // 3 + 1) if "dekad" in dd.columns else 0
        if "dekad" in dd.columns:
            sums = dd.groupby(["year", "month"]).pef_mm_usda_scs_fao.sum()
            tot = dd.groupby(["year", "month"]).pef_month_total_usda_scs_fao.first()
            check("suma de Pef de decenas = Pef del mes", np.allclose(sums, tot, atol=1e-6))
        hits = scan_privacy(DATA_DIR / "demo")
        check("privacidad: sin coordenadas finas ni correos en demo", not hits, str(hits))

        # CSV de suelo
        csvp = Path(td) / "suelo.csv"
        csvp.write_text(
            "parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,"
            "sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,"
            "effective_root_depth_cm,awc_mm_per_m,awc_method\n"
            "P-014,2025-03-12,0,20,Lab X,5.8,H2O_1:2.5,,,42,31,27,hidrometro,,,60,,\n")
        r = ingest_soil_csv("P-014", str(csvp))
        check("suelo: pH medido, MO desconocida (sin fila)",
                r["status"] == "ok" and "ph" in r["measured"] and "organic_matter" in r["unknown"], str(r))
        bad = Path(td) / "malo.csv"
        bad.write_text(
            "parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,"
            "sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,"
            "effective_root_depth_cm,awc_mm_per_m,awc_method\n"
            "P-014,2025-03-12,0,20,Lab X,5.8,,,,60,31,27,hidrometro,,,,,\n")
        r2 = ingest_soil_csv("P-014", str(bad))
        check("suelo: rechaza pH sin método y textura ≠ 100",
                r2["status"] == "failed" and len(r2["errors"]) >= 2, str(r2.get("errors")))

        # Catálogo
        if yaml is not None:
            cat = Path(td) / "crops.yaml"
            cat.write_text("- code: maiz\n  risk_thresholds:\n"
                        "  - {stage: FLOWERING, metric: dekad_exposure_mm, value: pending, citation: pending}\n")
            try:
                validate_catalog(str(cat), "production"); prod_fail = False
            except ValidationFailed:
                prod_fail = True
            check("catálogo: production falla con pending", prod_fail)
            check("catálogo: sandbox pasa y rotula provisional",
                    validate_catalog(str(cat), "sandbox")["label"] is not None)
    DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

    width = max(len(n) for n, _, _ in results)
    for n, c, e in results:
        print(("OK   " if c else "FALLA"), n.ljust(width), e)
    nfail = sum(1 for _, c, _ in results if not c)
    print(f"\n{len(results) - nfail}/{len(results)} pruebas OK"
            + ("" if HAS_PARQUET else "  (sin pyarrow: tablas en CSV)"))
    return 1 if nfail else 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="milpa_r1", description="R1 — Datos y evidencia (MILPA RESILIENTE 3.3)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("fetch-power"); p.add_argument("--zone", required=True)
    p.add_argument("--lat", type=float, required=True); p.add_argument("--lon", type=float, required=True)
    p.add_argument("--start", default="2001-01-01"); p.add_argument("--end", default="2025-12-31")

    p = sp.add_parser("fetch-imerg"); p.add_argument("--zone", required=True)
    p.add_argument("--geojson", required=True)
    p.add_argument("--start", default="2001-01-01"); p.add_argument("--end", default="2025-12-31")
    p.add_argument("--workers", type=int, default=4); p.add_argument("--force", action="store_true")

    p = sp.add_parser("curate"); p.add_argument("--zone", required=True)
    p.add_argument("--lat", type=float, required=True); p.add_argument("--lon", type=float, default=0)
    p.add_argument("--elev", type=float, required=True, help="elevación del DEM del sitio (m)")
    p.add_argument("--phi", type=float, default=None, help="fracción de fixed_fraction [Pendiente]")
    p.add_argument("--force", action="store_true")

    p = sp.add_parser("validate"); p.add_argument("--zone", required=True)
    p.add_argument("--lat", type=float, required=True); p.add_argument("--elev", type=float, required=True)
    p.add_argument("--station-csv", default=None)

    p = sp.add_parser("ingest-soil"); p.add_argument("--parcel", required=True); p.add_argument("--file", required=True)
    p = sp.add_parser("check-catalog"); p.add_argument("file"); p.add_argument("--mode", default=None)
    sp.add_parser("build-demo"); sp.add_parser("selftest")
    p = sp.add_parser("scan-privacy"); p.add_argument("path", nargs="?", default=str(DATA_DIR / "demo"))

    a = ap.parse_args(argv)
    try:
        if a.cmd == "fetch-power":
            fetch_power(a.zone, a.lat, a.lon, a.start, a.end); print("Descarga registrada en el manifiesto")
        elif a.cmd == "fetch-imerg":
            print(json.dumps(fetch_imerg(a.zone, a.geojson, a.start, a.end, a.workers, a.force),
                            indent=2, ensure_ascii=False))
        elif a.cmd == "curate":
            print(json.dumps(curate_zone(a.zone, a.lat, a.lon, a.elev, phi=a.phi, force=a.force), indent=2, ensure_ascii=False))
        elif a.cmd == "validate":
            print(json.dumps(validate_zone(a.zone, a.lat, a.elev, a.station_csv), indent=2, ensure_ascii=False))
        elif a.cmd == "ingest-soil":
            print(json.dumps(ingest_soil_csv(a.parcel, a.file), indent=2, ensure_ascii=False, default=str))
        elif a.cmd == "check-catalog":
            print(json.dumps(validate_catalog(a.file, a.mode), indent=2, ensure_ascii=False))
        elif a.cmd == "build-demo":
            print(json.dumps(build_demo(), indent=2, ensure_ascii=False))
        elif a.cmd == "scan-privacy":
            hits = scan_privacy(Path(a.path)); print("\n".join(hits) or "sin hallazgos"); return 1 if hits else 0
        elif a.cmd == "selftest":
            return selftest()
    except (ValidationFailed, NotImplementedError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
