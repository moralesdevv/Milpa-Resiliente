"""Fetch SoilGrids estimates for a 3x3 point grid inside Jocotan municipality."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
GEOJSON_PATH = ROOT / "data/regions/jocotan.geojson"
OUTPUT_DIR = ROOT / "data/soilgrids"
WEB_OUTPUT_DIR = ROOT / "apps/web/public/data/soilgrids"
API_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ("clay", "sand", "silt", "soc", "phh2o", "bdod")
DEPTH = "0-5cm"
VALUE = "mean"
MIN_REQUEST_INTERVAL_SECONDS = 12.0  # ISRIC fair use: max. 5 calls per minute.
REQUEST_TIMEOUT = (10, 45)

UNITS = {
    "clay": "%",
    "sand": "%",
    "silt": "%",
    "soc": "g/kg",
    "phh2o": "pH",
    "bdod": "kg/dm3",
}
DIVISORS = {
    "clay": 10.0,
    "sand": 10.0,
    "silt": 10.0,
    "soc": 10.0,
    "phh2o": 10.0,
    "bdod": 100.0,
}


def read_municipality(path: Path) -> Any:
    """Read, validate, and return the municipal geometry in WGS84."""
    frame = gpd.read_file(path)
    if frame.empty or frame.geometry.isna().all():
        raise ValueError(f"El GeoJSON no contiene geometrías: {path}")
    if frame.crs is None:
        frame = frame.set_crs("EPSG:4326")
    elif frame.crs.to_epsg() != 4326:
        frame = frame.to_crs("EPSG:4326")
    polygon = frame.geometry.union_all()
    if polygon.is_empty or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("La geometría municipal debe ser Polygon o MultiPolygon.")
    return polygon


def make_grid(polygon: Any) -> list[dict[str, Any]]:
    """Create 9 bbox grid points and retain only points strictly inside the polygon."""
    min_x, min_y, max_x, max_y = polygon.bounds
    offsets = (1 / 6, 1 / 2, 5 / 6)
    longitudes = [min_x + (max_x - min_x) * offset for offset in offsets]
    latitudes = [min_y + (max_y - min_y) * offset for offset in offsets]
    points = []
    for row, latitude in enumerate(latitudes, start=1):
        for column, longitude in enumerate(longitudes, start=1):
            point = Point(longitude, latitude)
            if polygon.contains(point):
                points.append(
                    {
                        "point_id": f"r{row}_c{column}",
                        "longitude": float(longitude),
                        "latitude": float(latitude),
                        "status": "not_queried",
                    }
                )
    return points


def _raw_value(payload: dict[str, Any], property_code: str) -> float | None:
    layers = payload.get("properties", {}).get("layers", [])
    layer = next((item for item in layers if item.get("name") == property_code), None)
    if layer is None:
        return None
    depth = next(
        (item for item in layer.get("depths", []) if item.get("label") == DEPTH),
        None,
    )
    raw = depth.get("values", {}).get(VALUE) if depth else None
    return float(raw) if isinstance(raw, int | float) else None


def convert_values(payload: dict[str, Any]) -> dict[str, float | None]:
    """Extract the requested SoilGrids values and convert mapped units."""
    return {
        code: (raw / DIVISORS[code] if (raw := _raw_value(payload, code)) is not None else None)
        for code in PROPERTIES
    }


def query_point(session: requests.Session, point: dict[str, Any]) -> dict[str, float | None]:
    """Query all six properties for one point in a single API call."""
    params: list[tuple[str, str | float]] = [
        ("lon", point["longitude"]),
        ("lat", point["latitude"]),
        *(("property", code) for code in PROPERTIES),
        ("depth", DEPTH),
        ("value", VALUE),
    ]
    response = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("SoilGrids devolvió una respuesta JSON inesperada.")
    return convert_values(payload)


def _wait_for_api_slot(last_started: float | None) -> float:
    if last_started is None:
        return time.monotonic()
    time.sleep(1.2)
    elapsed = time.monotonic() - last_started
    if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    return time.monotonic()


def _mean(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return float(sum(valid) / len(valid)) if valid else None


def build_average(points: list[dict[str, Any]], status: str) -> dict[str, Any]:
    properties = {}
    for code in PROPERTIES:
        values = [point.get(code) for point in points]
        properties[code] = {
            "value": _mean(values),
            "unit": UNITS[code],
            "valid_points": sum(value is not None for value in values),
        }
    return {
        "municipality": "Jocotán, Chiquimula, Guatemala",
        "source": "ISRIC SoilGrids v2.0",
        "endpoint": API_URL,
        "depth": DEPTH,
        "statistic": VALUE,
        "status": status,
        "status_detail": {
            "unavailable": "El servicio SoilGrids no devolvió respuesta utilizable; vuelve a ejecutar la ETL cuando el REST esté disponible.",
            "partial": "La consulta quedó incompleta; revisa manifest.json antes de usar los promedios.",
            "no_points": "La cuadrícula no produjo puntos estrictamente interiores al polígono.",
            "no_estimates": "El servicio respondió, pero no devolvió estimaciones para los puntos consultados.",
            "input_error": "No se pudo leer o validar el GeoJSON municipal.",
        }.get(status),
        "is_measured_soil": False,
        "note": (
            "Estimaciones espaciales del modelo SoilGrids a 250 m; "
            "no sustituyen un análisis de laboratorio ni describen cada parcela."
        ),
        "points_inside_polygon": len(points),
        "properties": properties,
    }


def save_outputs(points: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail = pd.DataFrame(points)
    detail.to_csv(OUTPUT_DIR / "jocotan_puntos_detalle.csv", index=False)
    average = build_average(points, str(manifest["status"]))
    average_json = json.dumps(average, ensure_ascii=False, indent=2) + "\n"
    (OUTPUT_DIR / "jocotan_promedio.json").write_text(average_json, encoding="utf-8")
    (WEB_OUTPUT_DIR / "jocotan_promedio.json").write_text(average_json, encoding="utf-8")
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run() -> int:
    """Run the SoilGrids extraction and write UI-ready data and provenance."""
    points: list[dict[str, Any]] = []
    errors: list[str] = []
    queried = 0
    successful = 0
    last_started = None
    status = "unavailable"
    print(f"Leyendo polígono municipal: {GEOJSON_PATH.relative_to(ROOT)}")
    try:
        polygon = read_municipality(GEOJSON_PATH)
        points = make_grid(polygon)
        print(f"Puntos estrictamente dentro del polígono: {len(points)}")
        if not points:
            status = "no_points"
        else:
            with requests.Session() as session:
                session.headers.update({"User-Agent": "MILPA-Resiliente/1.0 (SoilGrids ETL)"})
                for point in points:
                    try:
                        last_started = _wait_for_api_slot(last_started)
                        queried += 1
                        point.update(query_point(session, point))
                        point["status"] = "ok"
                        successful += 1
                        print(f"OK {point['point_id']}: consulta completada")
                    except (requests.RequestException, ValueError, KeyError) as exc:
                        message = f"{point['point_id']}: {type(exc).__name__}: {exc}"
                        point["status"] = "error"
                        point["error"] = message
                        errors.append(message)
                        print(f"ERROR {message}", file=sys.stderr)
                        break
            for point in points:
                for code in PROPERTIES:
                    point.setdefault(code, None)
            if errors:
                status = "unavailable" if successful == 0 else "partial"
            else:
                status = (
                    "ok"
                    if any(point.get(code) is not None for point in points for code in PROPERTIES)
                    else "no_estimates"
                )
    except (OSError, ValueError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        status = "input_error"
        print(errors[-1], file=sys.stderr)

    manifest = {
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "source": "ISRIC SoilGrids v2.0",
        "endpoint": API_URL,
        "geojson_used": "data/regions/jocotan.geojson",
        "crs": "EPSG:4326",
        "grid": "3x3 over polygon bounding box; polygon.contains(point)",
        "properties": list(PROPERTIES),
        "depth": DEPTH,
        "value": VALUE,
        "points_inside_polygon": len(points),
        "points_queried": queried,
        "successful_responses": successful,
        "status": status,
        "errors": errors,
        "api_fair_use": "maximum 5 requests per minute",
    }
    save_outputs(points, manifest)
    print(f"Estado ETL: {status}")
    print(f"Resultados: {OUTPUT_DIR.relative_to(ROOT)}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(run())
