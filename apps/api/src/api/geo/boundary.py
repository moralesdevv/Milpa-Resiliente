"""Límite municipal de referencia (GeoJSON) con validación estructural y huella SHA-256.

El archivo (``regions/jocotan_chiquimula_boundary.geojson``) es la ÚNICA fuente del polígono: la interfaz lo
empaqueta tal cual para dibujarlo y el servidor lo usa, con PostGIS (``ST_Covers``), para rechazar
ubicaciones fuera del municipio. Aquí solo se valida que el archivo sea utilizable; la validez topológica
final (``ST_IsValid``) la comprueba PostGIS en las pruebas de integración y en ``api.cli check-boundary``.

No se asume ninguna procedencia que el archivo no declare: ``source_note`` queda vacío si no consta.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

# Caja que contiene a Guatemala (grados). Una coordenada fuera de ella indica ejes invertidos o CRS distinto.
GUATEMALA_BBOX = (-92.3, 13.7, -88.2, 17.9)  # lon_min, lat_min, lon_max, lat_max
_ACCEPTED_CRS = {"EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:EPSG::4326"}


class BoundaryError(ValueError):
    """El archivo de límite no es utilizable (estructura, CRS o coordenadas)."""


@dataclass(frozen=True)
class MunicipalBoundary:
    name: str
    department: str
    municipal_code: int | None
    department_code: int | None
    geometry: dict[str, Any]
    sha256: str
    n_vertices: int
    bbox: tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max
    source_note: str

    @property
    def geometry_json(self) -> str:
        return json.dumps(self.geometry, separators=(",", ":"), sort_keys=True)

    @property
    def label(self) -> str:
        return f"{self.name}, {self.department}"


def _first(props: dict[str, Any], *keys: str) -> Any:
    return next((props[k] for k in keys if props.get(k) not in (None, "")), None)


def _check_ring(ring: Any, where: str) -> list[tuple[float, float]]:
    if not isinstance(ring, list) or len(ring) < 4:
        raise BoundaryError(f"{where}: un anillo necesita al menos 4 posiciones")
    points: list[tuple[float, float]] = []
    for position in ring:
        if (
            not isinstance(position, list | tuple)
            or len(position) < 2
            or not all(isinstance(v, int | float) and math.isfinite(v) for v in position[:2])
        ):
            raise BoundaryError(f"{where}: posición no numérica")
        lon, lat = float(position[0]), float(position[1])
        lon_min, lat_min, lon_max, lat_max = GUATEMALA_BBOX
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            raise BoundaryError(
                f"{where}: la coordenada ({lon}, {lat}) cae fuera de Guatemala; revise el orden lon,lat y el CRS"
            )
        points.append((lon, lat))
    if points[0] != points[-1]:
        raise BoundaryError(f"{where}: el anillo no está cerrado")
    return points


def _segments_cross(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]
) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2, d3, d4 = orient(c, d, a), orient(c, d, b), orient(a, b, c), orient(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


def _is_simple(points: list[tuple[float, float]]) -> bool:
    """Un anillo simple no se cruza a sí mismo (comprobación O(n²): los límites municipales tienen ~10² vértices)."""
    n = len(points) - 1
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # primer y último segmento comparten el vértice de cierre
            if _segments_cross(points[i], points[i + 1], points[j], points[j + 1]):
                return False
    return True


def parse_boundary(raw: bytes) -> MunicipalBoundary:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BoundaryError("El archivo no es JSON UTF-8 válido") from exc
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise BoundaryError("Se esperaba un FeatureCollection")
    crs = ((data.get("crs") or {}).get("properties") or {}).get("name")
    if crs is not None and crs not in _ACCEPTED_CRS:
        raise BoundaryError(f"CRS no admitido: {crs} (se requiere EPSG:4326)")
    features = data.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise BoundaryError("El archivo debe contener exactamente un Feature (un municipio)")
    feature = features[0]
    geometry = feature.get("geometry") if isinstance(feature, dict) else None
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise BoundaryError("La geometría debe ser Polygon o MultiPolygon")
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    n_vertices = 0
    lons: list[float] = []
    lats: list[float] = []
    for p_index, polygon in enumerate(polygons):
        if not isinstance(polygon, list) or not polygon:
            raise BoundaryError("Polígono vacío")
        for r_index, ring in enumerate(polygon):
            points = _check_ring(ring, f"polígono {p_index} anillo {r_index}")
            if not _is_simple(points):
                raise BoundaryError(f"polígono {p_index} anillo {r_index}: se cruza a sí mismo")
            n_vertices += len(points) - 1
            lons += [p[0] for p in points]
            lats += [p[1] for p in points]
    props = feature.get("properties") or {}
    name = _first(props, "NOMBRE_1", "NOMBRE", "name", "NAME")
    department = _first(props, "DEPTO_1", "DEPTO", "department", "DEPARTAMENTO")
    if not name or not department:
        raise BoundaryError(
            "Faltan el nombre del municipio y/o del departamento en las propiedades"
        )

    def as_int(value: Any) -> int | None:
        return (
            int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
        )

    return MunicipalBoundary(
        name=str(name),
        department=str(department),
        municipal_code=as_int(_first(props, "COD_MUN", "cod_mun")),
        department_code=as_int(_first(props, "COD_DEPTO", "cod_depto")),
        geometry=geometry,
        sha256=hashlib.sha256(raw).hexdigest(),
        n_vertices=n_vertices,
        bbox=(min(lons), min(lats), max(lons), max(lats)),
        source_note=str(_first(props, "source", "fuente", "SOURCE") or ""),
    )


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime_ns: int) -> MunicipalBoundary:
    del mtime_ns  # forma parte de la clave de caché: si el archivo cambia, se vuelve a validar
    return parse_boundary(Path(path).read_bytes())


def load_boundary(path: Path) -> MunicipalBoundary:
    try:
        stat = path.stat()
    except OSError as exc:
        raise BoundaryError(f"No se puede leer el límite municipal en {path}") from exc
    return _load_cached(str(path.resolve()), stat.st_mtime_ns)
