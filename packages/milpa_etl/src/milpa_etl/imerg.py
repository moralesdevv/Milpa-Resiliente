#!/usr/bin/env python3
"""
imerg_r1.py — DE-03: conector IMERG + fusión con la serie curada + comparación.

    Producto (verificado en las fichas oficiales, DP-16 parcial):
    GPM IMERG Final Run, diario, 0.1°, versión 07  ->  short_name GPM_3IMERGDF
    variable `precipitation` (mm/día, media diaria), `precipitation_cnt` (muestras válidas).
    Celdas sin muestras válidas vienen con valor de relleno (no es cero).
    NO verificado todavía: convención del día (el PDF dice día UTC; Guatemala es UTC-6),
    estructura exacta del archivo real y uso de EARTHDATA_TOKEN con earthaccess.
    Por eso existe el comando `check`, que imprime lo que realmente trae un archivo.

    Flujo:
    1. check   : inspecciona UN archivo real (evidencia para el ADR de DP-16)
    2. fetch   : descarga el recorte espacial de la zona por años, guarda raw con hash
    3. merge   : IMERG pasa a ser la lluvia primaria; POWER queda de respaldo (bit 32)
    4. validate-station : compara IMERG y POWER con un CSV de estación (opcional)
    5. register-cells   : registra las celdas y pesos en geo.climate_cell / geo.zone_cell

    Requiere milpa_r1.py en la misma carpeta.
    Dependencias: pandas, numpy, earthaccess, xarray, h5netcdf (psycopg para register-cells).
    pip install earthaccess xarray h5netcdf "psycopg[binary]"
    Credenciales: variable EARTHDATA_TOKEN (o archivo .env). Nunca en el repositorio.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from milpa_etl import core as r1

SHORT_NAME = "GPM_3IMERGDF"
VERSION = "07"
SOURCE_CODE = "IMERG_FINAL_V07"          # código en prov.data_source (apartado 13.2)
VARIABLE = "precipitation"
COUNT_VAR = "precipitation_cnt"
CELL_DEG = 0.1
DEFAULT_MIN_WEIGHT_COV = 0.5             # [Pendiente] DP-08/DP-09: fracción mínima de peso válido por día
F_MISSING, F_FALLBACK = r1.F_MISSING, r1.F_FALLBACK
IMERG_SOURCES = (SOURCE_CODE, "IMERG_FINAL")   # nombres con que aparece en el manifiesto
SPIKE_POWER_MM = 100.0      # umbrales de DIAGNÓSTICO (no de QC) para días atípicos de POWER
SPIKE_IMERG_MM = 10.0


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _retry(fn, retries: int = 3):
    for i in range(retries):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


def cell_index(lon, lat):
    """Índice entero de la celda de 0.1° que contiene el punto (robusto al ruido de coma flotante)."""
    ix = np.floor((np.asarray(lon, dtype=float) + 180.0) / CELL_DEG + 1e-9).astype(int)
    iy = np.floor((np.asarray(lat, dtype=float) + 90.0) / CELL_DEG + 1e-9).astype(int)
    return ix, iy


def cell_center(ix: int, iy: int) -> tuple[float, float]:
    return round((ix + 0.5) * CELL_DEG - 180.0, 3), round((iy + 0.5) * CELL_DEG - 90.0, 3)


def zdir(zone: str) -> Path:
    return r1.DATA_DIR / "curated" / zone


# ----------------------------------------------------------------------------
# Pesos de las celdas de 0.1° dentro de la zona (sin dependencias geoespaciales)
# ----------------------------------------------------------------------------
def zone_weights(geojson_path: str, n: int = 400) -> list[dict]:
    """Peso de cada celda = fracción del área de la zona que cae en ella.
    Se estima con una malla de n x n puntos dentro del polígono (regla par-impar).
    Es una aproximación (error ~ 1/n); PostGIS puede dar el valor exacto [Verificar]."""
    feat = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    geom = feat["geometry"] if feat.get("type") == "Feature" else feat
    if geom["type"] != "Polygon":
        raise ValueError("el GeoJSON debe ser un Polygon")
    rings = geom["coordinates"]
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    gx = x0 + (np.arange(n) + 0.5) * (x1 - x0) / n
    gy = y0 + (np.arange(n) + 0.5) * (y1 - y0) / n
    X, Y = np.meshgrid(gx, gy)
    X, Y = X.ravel(), Y.ravel()
    inside = np.zeros(X.shape, dtype=bool)
    for ring in rings:
        for (xa, ya), (xb, yb) in zip(ring[:-1], ring[1:], strict=False):
            cond = (ya > Y) != (yb > Y)
            with np.errstate(divide="ignore", invalid="ignore"):
                xint = (xb - xa) * (Y - ya) / (yb - ya) + xa
            inside ^= cond & (X < xint)
    if not inside.any():
        raise ValueError("el polígono no contiene puntos de muestra; revise las coordenadas")
    ix, iy = cell_index(X[inside], Y[inside])
    keys, counts = np.unique(ix * 100000 + iy, return_counts=True)
    total = counts.sum()
    out = []
    for k, c in zip(keys, counts, strict=False):
        cx, cy = int(k // 100000), int(k % 100000)
        lon_c, lat_c = cell_center(cx, cy)
        out.append({"ix": cx, "iy": cy, "lon": lon_c, "lat": lat_c, "weight": float(c / total)})
    return out


def bbox_from_weights(weights: list[dict]) -> list[float]:
    half = CELL_DEG / 2
    return [round(min(w["lon"] for w in weights) - half, 3), round(min(w["lat"] for w in weights) - half, 3),
            round(max(w["lon"] for w in weights) + half, 3), round(max(w["lat"] for w in weights) + half, 3)]


# ----------------------------------------------------------------------------
# Lectura de un archivo IMERG (necesita xarray + h5netcdf; NO probado aquí)
# ----------------------------------------------------------------------------
DATE_IN_NAME = re.compile(r"3IMERG\.(\d{8})")
VERSION_IN_NAME = re.compile(r"\.(V\d{2}[A-Z]?)\.")


def read_granule(fobj, name: str, bbox: list[float]) -> tuple[pd.DataFrame, dict]:
    import xarray as xr  # import tardío: solo se necesita al leer archivos reales

    ds, errors = None, []
    for group in (None, "Grid"):
        try:
            d = xr.open_dataset(fobj, engine="h5netcdf", group=group) if group else \
                xr.open_dataset(fobj, engine="h5netcdf")
        except Exception as e:  # noqa: BLE001
            errors.append(f"grupo={group or 'raíz'}: {type(e).__name__}: {e}"[:400])
            continue
        if VARIABLE in d.variables:
            ds = d
            break
        errors.append(f"grupo={group or 'raíz'}: abre bien pero sus variables son {sorted(d.variables)[:40]}")
        d.close()
    if ds is None:
        raise KeyError(f"no se pudo leer {VARIABLE!r} en {name}. Detalle: " + " | ".join(errors))
    lon_v, lat_v = ds["lon"].values, ds["lat"].values
    lon_sl = slice(bbox[0], bbox[2]) if lon_v[0] < lon_v[-1] else slice(bbox[2], bbox[0])
    lat_sl = slice(bbox[1], bbox[3]) if lat_v[0] < lat_v[-1] else slice(bbox[3], bbox[1])
    vars_ = [VARIABLE] + ([COUNT_VAR] if COUNT_VAR in ds.variables else [])
    sub = ds[vars_].sel(lon=lon_sl, lat=lat_sl)
    df = sub.to_dataframe().reset_index()
    if df.empty:
        raise ValueError("recorte vacío: ¿bbox fuera de la rejilla o ejes invertidos?")
    m = DATE_IN_NAME.search(name)
    day = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else str(df["time"].iloc[0])[:10]
    df["date"] = day
    df["lon"], df["lat"] = df["lon"].round(3), df["lat"].round(3)
    df = df.rename(columns={VARIABLE: "precipitation"})
    df.loc[df["precipitation"] < 0, "precipitation"] = np.nan   # un relleno negativo no es lluvia
    if COUNT_VAR not in df.columns:
        df[COUNT_VAR] = np.nan
    info = {"units": str(ds[VARIABLE].attrs.get("units", "")),
            "fill_value": str(ds[VARIABLE].encoding.get("_FillValue")),
            "dims": {k: int(v) for k, v in ds[VARIABLE].sizes.items()},
            "version_in_name": (VERSION_IN_NAME.search(name).group(1) if VERSION_IN_NAME.search(name) else None)}
    ds.close()
    return df[["date", "lon", "lat", "precipitation", COUNT_VAR]], info


def _earthaccess_login():
    try:
        import earthaccess
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError("Falta earthaccess: pip install earthaccess xarray h5netcdf") from e
    load_env()
    for strategy in ("environment", "netrc"):
        try:
            auth = earthaccess.login(strategy=strategy)
            if getattr(auth, "authenticated", False):
                return earthaccess
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("No se pudo iniciar sesión en Earthdata. Define EARTHDATA_TOKEN "
                       "(variable de entorno o .env) y verifica que no haya vencido. [Verificar] "
                       "que tu versión de earthaccess acepte EARTHDATA_TOKEN.")


def check_one_day(day: str, geojson: str, download: bool = False) -> int:
    """Inspecciona UN archivo real. Su salida sirve para el ADR de DP-16."""
    ea = _earthaccess_login()
    weights = zone_weights(geojson)
    bbox = bbox_from_weights(weights)
    res = ea.search_data(short_name=SHORT_NAME, version=VERSION, temporal=(day, day), bounding_box=tuple(bbox))
    print(f"granules encontrados: {len(res)}")
    if not res:
        return 2
    name = res[0].data_links()[0].split("/")[-1]
    print("archivo:", name)
    if download:
        tmp = r1.DATA_DIR / "tmp_imerg"
        tmp.mkdir(parents=True, exist_ok=True)
        f = str(ea.download(res[:1], local_path=str(tmp))[0])
        print("descargado a:", f)
    else:
        f = ea.open(res[:1])[0]
    df, info = read_granule(f, name, bbox)
    print("info:", json.dumps(info, ensure_ascii=False))
    print("celdas devueltas:", len(df), "| con dato:", int(df.precipitation.notna().sum()))
    print(df.head(12).to_string(index=False))
    print("\nCompara 'units' con mm/day y 'fill_value' con la ficha oficial; anótalo en el ADR (DP-16).")
    return 0


# ----------------------------------------------------------------------------
# Descarga por años (recorte espacial en origen) con raw inmutable y manifiesto
# ----------------------------------------------------------------------------
def _already_ok(zone: str, year: int, t0: str, t1: str, bbox: list[float]) -> bool:
    for e in r1.read_manifest():
        p = e.get("params", {})
        if (e.get("source") == SOURCE_CODE and e.get("status") == "ok" and p.get("zone") == zone
                and p.get("year") == year and p.get("period_start") == t0 and p.get("period_end") == t1
                and p.get("bbox") == bbox and p.get("version") == VERSION):
            return True
    return False


def fetch_imerg(zone: str, geojson: str, start: str, end: str, force: bool = False,
                batch: int = 20, retries: int = 3, download: bool = False) -> None:
    ea = _earthaccess_login()
    weights = zone_weights(geojson)
    bbox = bbox_from_weights(weights)
    zdir(zone).mkdir(parents=True, exist_ok=True)
    (zdir(zone) / "imerg_weights.json").write_text(
        json.dumps({"zone": zone, "cell_deg": CELL_DEG, "bbox": bbox, "cells": weights,
                    "method": "malla de 400x400 puntos dentro del polígono (aproximado)"},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(weights)} celdas de 0.1° cubren la zona; bbox {bbox}")

    y0, y1 = int(start[:4]), int(end[:4])
    for year in range(y0, y1 + 1):
        t0, t1 = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        params = {"zone": zone, "year": year, "period_start": t0, "period_end": t1, "bbox": bbox,
                  "short_name": SHORT_NAME, "version": VERSION, "variable": VARIABLE}
        if not force and _already_ok(zone, year, t0, t1, bbox):
            print(f"{year}: ya descargado (use --force para repetir)")
            continue
        t_start = time.time()
        try:
            results = _retry(lambda t0=t0, t1=t1: ea.search_data(short_name=SHORT_NAME, version=VERSION,
                                                     temporal=(t0, t1), bounding_box=tuple(bbox)), retries)
        except Exception as e:  # noqa: BLE001
            r1.log_ingestion(source=SOURCE_CODE, product=SHORT_NAME, version=VERSION, params=params,
                             raw_uri="", raw_sha256="", n_records=0, status="failed",
                             report={"error": f"búsqueda: {e}"[:300]})
            print(f"{year}: falló la búsqueda ({e})")
            continue
        frames, failed, versions, units, fills = [], [], set(), set(), set()
        for i in range(0, len(results), batch):
            chunk = results[i:i + batch]
            try:
                if download:
                    tmp = r1.DATA_DIR / "tmp_imerg"
                    tmp.mkdir(parents=True, exist_ok=True)
                    files = [str(x) for x in _retry(lambda c=chunk, tmp=tmp: ea.download(c, local_path=str(tmp)), retries)]
                else:
                    files = _retry(lambda c=chunk: ea.open(c), retries)
            except Exception as e:  # noqa: BLE001
                failed += [{"granule": g.data_links()[0].split("/")[-1], "error": f"open: {e}"[:150]} for g in chunk]
                continue
            for g, f in zip(chunk, files, strict=False):
                name = g.data_links()[0].split("/")[-1]
                try:
                    df, info = read_granule(f, name, bbox)
                    frames.append(df)
                    units.add(info["units"]); fills.add(info["fill_value"])
                    if info["version_in_name"]:
                        versions.add(info["version_in_name"])
                except Exception as e:  # noqa: BLE001
                    failed.append({"granule": name, "error": str(e)[:150]})
                finally:
                    try:
                        if isinstance(f, str):
                            os.remove(f)          # el archivo global ya no hace falta: solo se guarda el recorte
                        else:
                            f.close()
                    except Exception:  # noqa: BLE001
                        pass
            print(f"  {year}: {min(i + batch, len(results))}/{len(results)} archivos "
                  f"({(time.time() - t_start) / 60:.1f} min)")
        if not frames:
            r1.log_ingestion(source=SOURCE_CODE, product=SHORT_NAME, version=VERSION, params=params,
                             raw_uri="", raw_sha256="", n_records=0, status="failed",
                             report={"granules": len(results), "failed": failed[:20]})
            print(f"{year}: sin datos")
            continue
        data = pd.concat(frames, ignore_index=True).sort_values(["date", "lat", "lon"])
        digest, path = r1.save_raw("imerg", data.to_csv(index=False, float_format="%.4f").encode("utf-8"))
        expected = {d.strftime("%Y-%m-%d") for d in pd.date_range(t0, t1, freq="D")}
        missing = sorted(expected - set(data["date"]))
        status = "ok" if not failed and not missing else "partial"
        r1.log_ingestion(
            source=SOURCE_CODE, product=SHORT_NAME, version=VERSION, params=params, raw_uri=path,
            raw_sha256=digest, n_records=int(len(data)), status=status,
            report={"granules": len(results), "failed": failed[:20], "n_failed": len(failed),
                    "missing_dates": missing[:30], "n_missing_dates": len(missing),
                    "versions_in_filenames": sorted(versions), "units_seen": sorted(units),
                    "fill_values_seen": sorted(fills),
                    "limitations": ["convención de día UTC frente a UTC-6 [Verificar]"]})
        print(f"{year}: {status} — {len(data)} filas, {len(missing)} fechas sin archivo, {len(failed)} fallas")


# ----------------------------------------------------------------------------
# Serie de la zona y fusión con la serie curada
# ----------------------------------------------------------------------------
def load_imerg_series(zone: str, weights: list[dict] | None, min_weight_cov: float):
    """Serie diaria zonal de IMERG a partir del manifiesto. Entiende dos formatos de raw:
      - JSON zonal (el que escribe `milpa_r1.py fetch-imerg`): filas {date, precip_mm, n_valid_cells}
        y la lista de celdas. Aquí `min_weight_cov` es la FRACCIÓN DE CELDAS con dato (el raw no dice
        cuáles celdas eran válidas, solo cuántas).
      - CSV por celdas (el de `imerg_r1.py fetch`): se pondera por área con `weights`.
    Se combinan TODAS las ingestas de la zona; si una fecha aparece dos veces, gana la más reciente."""
    entries = [e for e in r1.read_manifest()
               if e.get("source") in IMERG_SOURCES and e.get("params", {}).get("zone") == zone
               and e.get("status") in ("ok", "partial") and e.get("raw_sha256")]
    if not entries:
        raise r1.ValidationFailed(f"no hay ingestas IMERG ok/partial para la zona {zone}; ejecute fetch-imerg")
    parts, hashes, formats, n_cells = [], [], set(), set()
    for e in entries:                                    # el manifiesto es cronológico
        path = Path(e["raw_uri"])
        if not path.exists():
            path = r1.DATA_DIR / "raw" / "imerg" / e["raw_sha256"]
        text = path.read_text(encoding="utf-8")
        hashes.append(e["raw_sha256"])
        if text.lstrip().startswith("{"):
            raw = json.loads(text)
            formats.add("json_zonal")
            rows = pd.DataFrame(raw.get("rows", []))
            if rows.empty:
                continue
            nc = len(raw.get("cells", []))
            n_cells.add(nc)
            v = pd.to_numeric(rows["precip_mm"], errors="coerce")
            if nc and "n_valid_cells" in rows.columns:
                frac = pd.to_numeric(rows["n_valid_cells"], errors="coerce") / nc
                v = v.where(frac >= min_weight_cov)
            parts.append(pd.Series(v.values, index=pd.to_datetime(rows["date"])))
        else:
            formats.add("csv_celdas")
            if weights is None:
                raise r1.ValidationFailed("el raw en CSV necesita imerg_weights.json (ejecute imerg_r1.py fetch)")
            n_cells.add(len(weights))
            parts.append(zone_series(pd.read_csv(io.StringIO(text)), weights, min_weight_cov))
    if not parts:
        raise r1.ValidationFailed("las ingestas IMERG no contienen filas")
    s_ = pd.concat(parts)
    s_ = s_[~s_.index.duplicated(keep="last")].sort_index()
    s_.name = "precip_imerg_mm"
    return s_, sorted(set(hashes)), {"n_cells": max(n_cells) if n_cells else 0,
                                      "formats": sorted(formats), "n_entries": len(entries)}


def zone_series(df: pd.DataFrame, weights: list[dict], min_weight_cov: float) -> pd.Series:
    """Media ponderada por área de las celdas con dato. Un día es válido solo si las celdas con dato
    suman al menos `min_weight_cov` del peso de la zona; si no, queda faltante (nunca cero)."""
    wmap = {w["ix"] * 100000 + w["iy"]: w["weight"] for w in weights}
    ix, iy = cell_index(df["lon"].values, df["lat"].values)
    d = df.assign(w=pd.Series(ix * 100000 + iy, index=df.index).map(wmap))
    d = d[d["w"].notna()].copy()
    valid = d["precipitation"].notna().values
    d["wv"] = np.where(valid, d["w"], 0.0)
    d["wp"] = np.where(valid, d["w"] * d["precipitation"].fillna(0.0), 0.0)
    g = d.groupby("date")[["wv", "wp"]].sum()
    out = (g["wp"] / g["wv"].where(g["wv"] > 0)).where(g["wv"] >= min_weight_cov)
    out.index = pd.to_datetime(out.index)
    out.name = "precip_imerg_mm"
    return out


def _coverage_rows(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for var in cols:
        g = df[var].groupby(df.index.year)
        n_exp, n_val = g.size(), g.count()
        for y in n_exp.index:
            rows.append({"variable": var, "year": int(y), "n_expected": int(n_exp[y]),
                         "n_valid": int(n_val[y]),
                         "pct_missing": round(100 * (1 - n_val[y] / n_exp[y]), 3)})
    return pd.DataFrame(rows)


def compare_precip(imerg: pd.Series, power: pd.Series) -> dict:
    both = imerg.notna() & power.notna()
    a, b = imerg.where(both), power.where(both)
    out: dict = {"n_days_compared": int(both.sum()),
                 "note": "IMERG y POWER son productos de grilla gruesa; coincidir entre ellos NO es validar "
                         "en la zona (eso requiere una estación)"}
    if both.sum() < 30:
        out["status"] = "insuficiente: menos de 30 días en común"
        return out
    out["corr_daily"] = round(float(a.corr(b)), 3)
    out["bias_mm_day_imerg_minus_power"] = round(float((a - b).mean()), 3)
    out["ratio_total_imerg_over_power"] = round(float(a.sum() / b.sum()), 3) if b.sum() > 0 else None
    out["wet_day_freq_ge_1mm"] = {"imerg": round(float((a >= 1).sum() / both.sum()), 3),
                                  "power": round(float((b >= 1).sum() / both.sum()), 3)}
    dk = pd.DataFrame({"a": a, "b": b})
    dk["year"], dk["dekad"] = dk.index.year, r1.dekad_of_day(dk.index)
    g = dk.groupby(["year", "dekad"]).agg(a=("a", "sum"), b=("b", "sum"), n=("a", "count"), size=("a", "size"))
    g = g[g["n"] == g["size"]]
    if len(g) > 10:
        out["corr_dekad_sum"] = round(float(g["a"].corr(g["b"])), 3)
    full = dk.groupby("year").agg(a=("a", "sum"), b=("b", "sum"), n=("a", "count"), size=("a", "size"))
    full = full[full["n"] == full["size"]]
    out["annual_totals_mm"] = {int(y): {"imerg": round(float(r.a), 1), "power": round(float(r.b), 1),
                                        "ratio": round(float(r.a / r.b), 3) if r.b > 0 else None}
                               for y, r in full.iterrows()}
    out["monthly_bias_mm_day"] = {int(m): round(float(v), 3) for m, v in
                                  (a - b).groupby((a - b).index.month).mean().items()}
    return out


def _update_precip_validation(zone: str, key: str, value: dict) -> Path:
    p = zdir(zone) / "precip_validation.json"
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    cur[key] = value
    p.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def power_spike_report(imerg: pd.Series, power: pd.Series) -> dict:
    """Días en que POWER da lluvia enorme y IMERG casi nada. Es un DIAGNÓSTICO, no una corrección."""
    both = imerg.notna() & power.notna()
    sp = both & (power >= SPIKE_POWER_MM) & (imerg < SPIKE_IMERG_MM)
    top = power[sp].nlargest(10)
    by_year = power[sp].groupby(power[sp].index.year).sum().round(1)
    return {"definicion": f"POWER >= {SPIKE_POWER_MM:g} mm y IMERG < {SPIKE_IMERG_MM:g} mm el mismo día "
                          "(umbrales de diagnóstico, no de QC)",
            "n_days": int(sp.sum()),
            "top": [{"date": d.strftime("%Y-%m-%d"), "power_mm": round(float(v), 1),
                     "imerg_mm": round(float(imerg[d]), 1)} for d, v in top.items()],
            "power_mm_en_esos_dias_por_anio": {int(y): float(v) for y, v in by_year.items()}}


def merge_imerg(zone: str, min_weight_cov: float = DEFAULT_MIN_WEIGHT_COV, phi: float | None = None,
                max_fallback_mm: float | None = None) -> dict:
    """IMERG primaria, POWER de respaldo (bit 32). Reescribe daily, dekad, coverage y la meta.
    max_fallback_mm: si se indica, un día de respaldo con POWER por encima de ese valor queda faltante
    en vez de usarse (decisión metodológica pendiente, DP-08)."""
    zd = zdir(zone)
    meta_p = zd / "curated_meta.json"
    wp = zd / "imerg_weights.json"
    if not meta_p.exists():
        raise r1.ValidationFailed("falta la serie curada; ejecute milpa_r1.py curate primero")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    weights = json.loads(wp.read_text(encoding="utf-8"))["cells"] if wp.exists() else None
    daily = r1.read_table(zd / "daily")
    daily.index = pd.to_datetime(daily.index)

    series, hashes, info = load_imerg_series(zone, weights, min_weight_cov)
    imerg = series.reindex(daily.index)
    power = daily["precip_power_mm"] if "precip_power_mm" in daily.columns else daily["precip_mm"]

    used_fallback = imerg.isna() & power.notna()
    capped = pd.Series(False, index=daily.index)
    if max_fallback_mm is not None:
        capped = used_fallback & (power > max_fallback_mm)
        used_fallback = used_fallback & ~capped
    final = imerg.where(imerg.notna(), power.where(~capped))
    source = pd.Series(np.where(imerg.notna(), SOURCE_CODE,
                                np.where(used_fallback, "POWER_PRECTOTCORR", "none")), index=daily.index)
    flags = daily["qc_flags"].astype("int32")
    flags = flags - (flags & F_FALLBACK)                     # idempotente: se recalcula el bit 32
    flags = flags | (used_fallback.astype("int32") * F_FALLBACK) | (final.isna().astype("int32") * F_MISSING)

    daily["precip_power_mm"], daily["precip_imerg_mm"] = power, imerg
    daily["precip_mm"], daily["precip_source"], daily["qc_flags"] = final, source, flags.astype("int32")

    dekad = r1.build_dekad(daily, phi)
    cov_old = r1.read_table(zd / "coverage")
    cov_new = _coverage_rows(daily, ["precip_mm", "precip_imerg_mm"])
    cov = pd.concat([cov_old[~cov_old["variable"].isin(["precip_mm", "precip_imerg_mm"])], cov_new],
                    ignore_index=True)
    r1.write_table(daily, zd / "daily")
    r1.write_table(dekad, zd / "dekad")
    r1.write_table(cov, zd / "coverage")

    n_fb, n_cap = int(used_fallback.sum()), int(capped.sum())
    # ventana de IMERG: del primer al último día con dato; ahí se mide el respaldo (fuera de ella no hay IMERG que esperar)
    iv = imerg.dropna().index
    w0, w1 = iv.min(), iv.max()
    in_win = (daily.index >= w0) & (daily.index <= w1)
    n_win = int(in_win.sum())
    n_fb_win = int((used_fallback & in_win).sum())
    spikes = power_spike_report(imerg, power)
    power_hashes = meta.get("raw_sha256_power") or meta.get("raw_sha256", [])
    all_hashes = sorted(set(power_hashes) | set(hashes))
    imerg_missing = round(100 * float(imerg.isna().mean()), 3)
    limits = ["convención de día de POWER e IMERG frente a UTC-6 [Verificar]",
              "evidencia de lluvia: B solo con validación en la zona (estación); sin ella, C"]
    if spikes["n_days"]:
        limits.append(f"POWER tiene {spikes['n_days']} días atípicos (>= {SPIKE_POWER_MM:g} mm con IMERG "
                      f"< {SPIKE_IMERG_MM:g} mm); su lluvia como respaldo es poco confiable")
    meta.update({
        "precip_primary": SOURCE_CODE, "precip_fallback": "POWER_DAILY",
        "fallback_days": n_fb, "fallback_share_pct": round(100 * n_fb_win / max(n_win, 1), 3),
        "fallback_share_pct_full_series": round(100 * n_fb / len(daily), 3),
        "imerg_window": [w0.strftime("%Y-%m-%d"), w1.strftime("%Y-%m-%d")],
        "imerg_window_days": n_win, "imerg_window_fallback_days": n_fb_win,
        "fallback_cap_mm": max_fallback_mm, "fallback_days_capped": n_cap,
        "power_spike_days": spikes["n_days"],
        "days_without_precip": int(final.isna().sum()), "imerg_missing_pct": imerg_missing,
        "min_weight_cov": min_weight_cov, "imerg_n_cells": info["n_cells"],
        "imerg_formats": info["formats"],
        "raw_sha256_power": power_hashes, "raw_sha256_imerg": hashes, "raw_sha256": all_hashes,
        "data_hash": r1.sha256_bytes((",".join(all_hashes) + r1.logical_hash(daily)).encode()),
        "limitations": limits,
    })
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    cmp_ = compare_precip(imerg, power)
    _update_precip_validation(zone, "IMERG_vs_POWER", cmp_)
    _update_precip_validation(zone, "POWER_spikes", spikes)
    return {"zone": zone, "data_hash": meta["data_hash"], "fallback_days": n_fb,
            "fallback_days_capped": n_cap, "fallback_share_pct": meta["fallback_share_pct"], "imerg_window": meta["imerg_window"],
            "imerg_missing_pct_full_series": imerg_missing, "days_without_precip": meta["days_without_precip"],
            "power_spike_days": spikes["n_days"], "comparison": cmp_}


def validate_station(zone: str, station_csv: str) -> dict:
    """Compara IMERG y POWER con una estación (columnas: date, precip_mm). Es la validación en la zona."""
    daily = r1.read_table(zdir(zone) / "daily")
    daily.index = pd.to_datetime(daily.index)
    if "precip_imerg_mm" not in daily.columns:
        raise r1.ValidationFailed("ejecute merge antes de validar contra estación")
    st = pd.read_csv(station_csv, parse_dates=["date"]).set_index("date")["precip_mm"]
    res = {}
    for key, col in (("IMERG_vs_station", "precip_imerg_mm"), ("POWER_vs_station", "precip_power_mm")):
        j = pd.concat([daily[col], st], axis=1, keys=["sat", "station"]).dropna()
        if len(j) < 30:
            res[key] = {"status": "insuficiente: menos de 30 días en común", "n": int(len(j))}
            continue
        res[key] = {"n": int(len(j)), "corr_daily": round(float(j.corr().iloc[0, 1]), 3),
                    "bias_mm_day_sat_minus_station": round(float((j.sat - j.station).mean()), 3),
                    "ratio_total_sat_over_station": round(float(j.sat.sum() / j.station.sum()), 3)
                    if j.station.sum() > 0 else None}
        _update_precip_validation(zone, key, res[key])
    return res


# ----------------------------------------------------------------------------
# Registro de celdas en PostGIS
# ----------------------------------------------------------------------------
def register_cells(zone: str) -> None:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("define DATABASE_URL (variable de entorno o .env)")
    import psycopg

    cells = json.loads((zdir(zone) / "imerg_weights.json").read_text(encoding="utf-8"))["cells"]
    half = CELL_DEG / 2
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT source_id FROM prov.data_source WHERE code = %s", (SOURCE_CODE,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"falta {SOURCE_CODE} en prov.data_source (ejecute sql/93_seed_imerg.sql)")
        sid = row[0]
        cur.execute("SELECT zone_id FROM geo.zone WHERE name = %s", (zone,))
        z = cur.fetchone()
        if not z:
            raise RuntimeError(f"la zona {zone} no existe en geo.zone (ejecute registrar_zona.py)")
        zone_id = z[0]
        for c in cells:
            cur.execute("""INSERT INTO geo.climate_cell (source_id, centroid, footprint)
                           VALUES (%(s)s, ST_SetSRID(ST_MakePoint(%(lo)s, %(la)s), 4326),
                                   ST_MakeEnvelope(%(lo)s - %(h)s, %(la)s - %(h)s, %(lo)s + %(h)s, %(la)s + %(h)s, 4326))
                           ON CONFLICT (source_id, centroid) DO NOTHING""",
                        {"s": sid, "lo": c["lon"], "la": c["lat"], "h": half})
            cur.execute("""SELECT cell_id FROM geo.climate_cell
                           WHERE source_id = %s AND centroid = ST_SetSRID(ST_MakePoint(%s, %s), 4326)""",
                        (sid, c["lon"], c["lat"]))
            cell_id = cur.fetchone()[0]
            cur.execute("""INSERT INTO geo.zone_cell (zone_id, cell_id, weight) VALUES (%s, %s, %s)
                           ON CONFLICT (zone_id, cell_id) DO UPDATE SET weight = EXCLUDED.weight""",
                        (zone_id, cell_id, min(max(c["weight"], 1e-6), 1.0)))
    print(f"{len(cells)} celdas IMERG registradas para {zone}")


# ----------------------------------------------------------------------------
# Autoprueba (sin red, sin xarray)
# ----------------------------------------------------------------------------
def selftest() -> int:
    import tempfile

    results = []

    def check(name, cond, extra=""):
        results.append((name, bool(cond), extra))

    gj = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [
        [[-89.60, 14.75], [-89.20, 14.75], [-89.20, 14.95], [-89.60, 14.95], [-89.60, 14.75]]]}}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        old = r1.DATA_DIR
        r1.DATA_DIR = td / "data"
        try:
            gp = td / "z.geojson"
            gp.write_text(json.dumps(gj), encoding="utf-8")
            w = zone_weights(str(gp))
            check("pesos suman 1", abs(sum(c["weight"] for c in w) - 1) < 1e-9)
            check("12 celdas para el rectángulo de prueba", len(w) == 12, str(len(w)))
            mid = [c for c in w if c["lat"] == 14.85]
            check("pesos esperados (fila central 0.125 por celda)",
                  len(mid) == 4 and all(abs(c["weight"] - 0.125) < 1e-6 for c in mid),
                  str([round(c["weight"], 4) for c in mid]))
            check("centros en la rejilla de IMERG (x.x5)",
                  all(abs(((c["lon"] + 180) / 0.1) % 1 - 0.5) < 1e-6 for c in w))
            bbox = bbox_from_weights(w)
            check("bbox cubre las celdas", bbox == [-89.6, 14.7, -89.2, 15.0], str(bbox))

            # serie POWER sintética curada
            zone = "zz"
            data = r1.synthetic_power_json(seed=3)
            raw_b = json.dumps(data, sort_keys=True).encode()
            dg, rp = r1.save_raw("power", raw_b)
            r1.log_ingestion(source="POWER_DAILY", product="sint", version=None, params={"zone": zone},
                             raw_uri=rp, raw_sha256=dg, n_records=9131, status="ok")
            r1.curate_from_power_json(zone, data, [dg], lat=14.8, elev_m=762.46, force=True)
            d0 = r1.read_table(zdir(zone) / "daily")
            d0.index = pd.to_datetime(d0.index)
            power = d0["precip_mm"].copy()
            (zdir(zone) / "imerg_weights.json").write_text(
                json.dumps({"zone": zone, "cells": w, "bbox": bbox}), encoding="utf-8")

            # IMERG sintético: 1.2 x POWER en todas las celdas, para 3 años
            def make_year(year):
                rows = []
                for day in pd.date_range(f"{year}-01-01", f"{year}-12-31"):
                    base = power.get(day, np.nan)
                    for c in w:
                        v = 1.2 * base if pd.notna(base) else np.nan
                        rows.append((day.strftime("%Y-%m-%d"), c["lon"], c["lat"], v, 48.0))
                return pd.DataFrame(rows, columns=["date", "lon", "lat", "precipitation", COUNT_VAR])

            special = "2005-07-15"
            for year in (2001, 2002, 2005):
                df = make_year(year)
                if year == 2001:      # 2001-03-10 a 12: sin archivo (filas ausentes) -> respaldo
                    df = df[~df["date"].isin(["2001-03-10", "2001-03-11", "2001-03-12"])]
                    # 2001-04-05: solo celdas de las esquinas con dato (peso 0.25 < 0.5) -> respaldo
                    corner = {(-89.55, 14.75), (-89.25, 14.75), (-89.55, 14.95), (-89.25, 14.95)}
                    m = df["date"] == "2001-04-05"
                    df.loc[m & ~df.apply(lambda r, corner=corner: (r.lon, r.lat) in corner, axis=1), "precipitation"] = np.nan
                    # 2001-05-01: una celda sin dato (peso 0.125 < 0.5 perdido) -> sigue válido, renormalizado
                    m2 = (df["date"] == "2001-05-01") & (df["lon"] == -89.55) & (df["lat"] == 14.85)
                    df.loc[m2, "precipitation"] = np.nan
                if year == 2005:      # valores distintos por celda para comprobar la media ponderada
                    m = df["date"] == special
                    df.loc[m, "precipitation"] = [float(i) ** 2 for i in range(m.sum())]
                dgi, rpi = r1.save_raw("imerg", df.to_csv(index=False, float_format="%.4f").encode())
                r1.log_ingestion(source=SOURCE_CODE, product=SHORT_NAME, version=VERSION,
                                 params={"zone": zone, "year": year, "period_start": f"{year}-01-01",
                                         "period_end": f"{year}-12-31", "bbox": bbox, "version": VERSION},
                                 raw_uri=rpi, raw_sha256=dgi, n_records=len(df), status="ok")

            out = merge_imerg(zone)
            d = r1.read_table(zdir(zone) / "daily")
            d.index = pd.to_datetime(d.index)
            check("lluvia primaria = 1.2 x POWER donde hay IMERG (2002-06-15)",
                  abs(d.loc["2002-06-15", "precip_mm"] - 1.2 * power["2002-06-15"]) < 1e-3)
            check("fuente = IMERG ese día", d.loc["2002-06-15", "precip_source"] == SOURCE_CODE)
            for day, why in (("2001-03-11", "sin archivo"), ("2001-04-05", "peso válido < 0.5"),
                             ("2010-06-15", "año sin descargar")):
                ok = (abs(d.loc[day, "precip_mm"] - power[day]) < 1e-9 or
                      (pd.isna(power[day]) and pd.isna(d.loc[day, "precip_mm"])))
                check(f"respaldo POWER con bit 32: {day} ({why})",
                      ok and (int(d.loc[day, "qc_flags"]) & 32) > 0 and d.loc[day, "precip_source"] != SOURCE_CODE)
            check("2001-05-01: una celda sin dato no invalida el día",
                  d.loc["2001-05-01", "precip_source"] == SOURCE_CODE and
                  abs(d.loc["2001-05-01", "precip_mm"] - 1.2 * power["2001-05-01"]) < 1e-3)
            vals = [float(i) ** 2 for i in range(12)]
            # el orden de filas del día especial es el de make_year (celdas en el orden de `w`)
            exp = sum(c["weight"] * v for c, v in zip(w, vals, strict=False))
            plain = float(np.mean(vals))
            check("media ponderada por área (distinta de la media simple)",
                  abs(d.loc[special, "precip_mm"] - exp) < 1e-3 and abs(exp - plain) > 0.1,
                  f"{d.loc[special, 'precip_mm']:.4f} vs esperado {exp:.4f} (simple {plain:.4f})")
            check("la lluvia nunca se rellena con cero",
                  not ((d["precip_mm"] == 0) & d["precip_power_mm"].isna() & d["precip_imerg_mm"].isna()).any())
            check("hash de datos presente", len(out["data_hash"]) == 64)
            c = out["comparison"]
            check("comparación: razón de totales ≈ 1.2", abs(c["ratio_total_imerg_over_power"] - 1.2) < 0.02,
                  str(c.get("ratio_total_imerg_over_power")))
            check("comparación: correlación ≈ 1", c["corr_daily"] > 0.99, str(c.get("corr_daily")))
            cov = r1.read_table(zdir(zone) / "coverage")
            check("cobertura incluye IMERG y lluvia primaria",
                  {"precip_mm", "precip_imerg_mm"} <= set(cov["variable"]))
            meta = json.loads((zdir(zone) / "curated_meta.json").read_text(encoding="utf-8"))
            check("meta registra fuente primaria y respaldo",
                  meta["precip_primary"] == SOURCE_CODE and meta["fallback_days"] > 0)
            out2 = merge_imerg(zone)
            check("idempotente: mismo data_hash al repetir", out2["data_hash"] == out["data_hash"])
            check("meta incluye hashes de ambas fuentes", len(meta["raw_sha256"]) >= 4, str(len(meta["raw_sha256"])))
            # estación
            st = pd.DataFrame({"date": power.index[:400], "precip_mm": power.values[:400] * 0.9})
            sp = td / "est.csv"
            st.to_csv(sp, index=False)
            vs = validate_station(zone, str(sp))
            check("validación contra estación escribe ambas comparaciones",
                  "IMERG_vs_station" in vs and "POWER_vs_station" in vs)

            # --- formato JSON zonal: el que escribe `milpa_r1.py fetch-imerg` (fuente IMERG_FINAL) ---
            zj = "zj"
            data2 = r1.synthetic_power_json(seed=5)
            pr = data2["properties"]["parameter"]["PRECTOTCORR"]
            pr["20010615"], pr["20010620"] = 300.0, 250.0           # dos días atípicos de POWER
            dg2, rp2 = r1.save_raw("power", json.dumps(data2, sort_keys=True).encode())
            r1.log_ingestion(source="POWER_DAILY", product="sint", version=None, params={"zone": zj},
                             raw_uri=rp2, raw_sha256=dg2, n_records=9131, status="ok")
            r1.curate_from_power_json(zj, data2, [dg2], lat=14.8, elev_m=762.46, force=True)
            d2 = r1.read_table(zdir(zj) / "daily")
            d2.index = pd.to_datetime(d2.index)
            pw = d2["precip_mm"]
            cells12 = [{"i": c["ix"], "j": c["iy"], "lon": c["lon"], "lat": c["lat"], "weight": c["weight"]} for c in w]

            def jrows(days):
                out_ = []
                for day in days:
                    k = day.strftime("%Y-%m-%d")
                    if k == "2001-06-20":
                        continue                                      # sin dato de IMERG -> respaldo con POWER
                    val = 2.0 if k == "2001-06-15" else (None if k == "2001-08-01" else
                                                         (float(round(1.2 * pw[day], 4)) if pd.notna(pw[day]) else None))
                    nv = 3 if k == "2001-07-01" else 12                # 3 de 12 celdas = 0.25 < 0.5 -> respaldo
                    out_.append({"date": k, "granule": "g", "n_valid_cells": nv, "precip_mm": val})
                return out_

            for rows_, a_, b_ in ((jrows(pd.date_range("2001-01-01", "2001-01-31")), "2001-01-01", "2001-01-31"),
                                  (jrows(pd.date_range("2001-02-01", "2001-12-31")), "2001-02-01", "2001-12-31"),
                                  ([{"date": "2001-01-01", "granule": "g", "n_valid_cells": 12, "precip_mm": 7.0}],
                                   "2001-01-01", "2001-01-01")):
                dgj, rpj = r1.save_raw("imerg", json.dumps({"cells": cells12, "rows": rows_}, sort_keys=True).encode())
                r1.log_ingestion(source="IMERG_FINAL", product=SHORT_NAME, version=VERSION,
                                 params={"zone": zj, "start": a_, "end": b_}, raw_uri=rpj, raw_sha256=dgj,
                                 n_records=len(rows_), status="ok")
            oj = merge_imerg(zj)
            dj = r1.read_table(zdir(zj) / "daily")
            dj.index = pd.to_datetime(dj.index)
            check("JSON zonal: combina ingestas y la más reciente gana (2001-01-01 = 7.0)",
                  abs(dj.loc["2001-01-01", "precip_mm"] - 7.0) < 1e-9)
            check("JSON zonal: no necesita imerg_weights.json y reconoce 12 celdas",
                  json.loads((zdir(zj) / "curated_meta.json").read_text())["imerg_n_cells"] == 12)
            check("JSON zonal: 3 de 12 celdas con dato -> respaldo POWER con bit 32 (2001-07-01)",
                  dj.loc["2001-07-01", "precip_source"] == "POWER_PRECTOTCORR" and (int(dj.loc["2001-07-01", "qc_flags"]) & 32) > 0)
            check("JSON zonal: lluvia nula en IMERG -> respaldo (2001-08-01)",
                  dj.loc["2001-08-01", "precip_source"] == "POWER_PRECTOTCORR")
            check("detecta días atípicos de POWER (300 mm con IMERG 2 mm)", oj["power_spike_days"] >= 1,
                  str(oj["power_spike_days"]))
            check("sin tope, el respaldo usa el atípico de POWER (2001-06-20 = 250)",
                  abs(dj.loc["2001-06-20", "precip_mm"] - 250.0) < 1e-6)
            oj2 = merge_imerg(zj, max_fallback_mm=150.0)
            dj2 = r1.read_table(zdir(zj) / "daily")
            dj2.index = pd.to_datetime(dj2.index)
            check("con tope de 150 mm, ese día queda faltante, sin bit 32 y con bit 1",
                  pd.isna(dj2.loc["2001-06-20", "precip_mm"]) and (int(dj2.loc["2001-06-20", "qc_flags"]) & 32) == 0
                  and (int(dj2.loc["2001-06-20", "qc_flags"]) & 1) > 0 and oj2["fallback_days_capped"] >= 1)
            check("fallback_share se mide en la ventana de IMERG, no en toda la serie",
                  json.loads((zdir(zj) / "curated_meta.json").read_text())["imerg_window_days"] > 0)
            check("el tope no toca los días con IMERG (2001-06-15 sigue en 2.0)",
                  abs(dj2.loc["2001-06-15", "precip_mm"] - 2.0) < 1e-9)
        finally:
            r1.DATA_DIR = old
    width = max(len(n) for n, _, _ in results)
    for n, c, e in results:
        print(("OK   " if c else "FALLA"), n.ljust(width), e)
    nf = sum(1 for _, c, _ in results if not c)
    print(f"\n{len(results) - nf}/{len(results)} pruebas OK  (la lectura de archivos reales de IMERG NO se prueba aquí)")
    return 1 if nf else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="imerg_r1", description="DE-03 IMERG")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("check", help="inspecciona un archivo real (DP-16)")
    p.add_argument("--day", default="2001-06-15"); p.add_argument("--geojson", required=True)
    p.add_argument("--download", action="store_true", help="descarga el archivo en vez de leerlo en línea")
    p = sp.add_parser("fetch")
    p.add_argument("--zone", required=True); p.add_argument("--geojson", required=True)
    p.add_argument("--start", default="2001-01-01"); p.add_argument("--end", default="2025-12-31")
    p.add_argument("--force", action="store_true")
    p.add_argument("--download", action="store_true", help="descarga cada archivo y lo borra tras recortarlo")
    p = sp.add_parser("merge")
    p.add_argument("--zone", required=True)
    p.add_argument("--min-weight-cov", type=float, default=DEFAULT_MIN_WEIGHT_COV)
    p.add_argument("--phi", type=float, default=None)
    p.add_argument("--max-fallback-mm", type=float, default=None,
                   help="días de respaldo con POWER por encima de este valor quedan faltantes [Pendiente DP-08]")
    p = sp.add_parser("validate-station")
    p.add_argument("--zone", required=True); p.add_argument("--station-csv", required=True)
    p = sp.add_parser("register-cells"); p.add_argument("--zone", required=True)
    sp.add_parser("selftest")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "check":
            return check_one_day(a.day, a.geojson, a.download)
        if a.cmd == "fetch":
            fetch_imerg(a.zone, a.geojson, a.start, a.end, a.force, download=a.download)
        elif a.cmd == "merge":
            print(json.dumps(merge_imerg(a.zone, a.min_weight_cov, a.phi, a.max_fallback_mm), indent=2, ensure_ascii=False))
        elif a.cmd == "validate-station":
            print(json.dumps(validate_station(a.zone, a.station_csv), indent=2, ensure_ascii=False))
        elif a.cmd == "register-cells":
            register_cells(a.zone)
        elif a.cmd == "selftest":
            return selftest()
    except (r1.ValidationFailed, RuntimeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
