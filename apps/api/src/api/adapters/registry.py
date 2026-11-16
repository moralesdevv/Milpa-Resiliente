"""Selección de adaptadores. Por defecto: dependencia no integrada.

Se usa ``MilpaCoreEngine`` solo si ``milpa_core`` está instalado Y cumple la fachada documentada.
Los métodos de ese adaptador siguen marcados PENDING_R2 hasta que R2 publique los contratos
faltantes, por lo que ninguna ruta devuelve datos de un motor "simulado".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from api.adapters.etl_process import ProcessIngest, ZoneSpec
from api.adapters.milpa_core import CoreAssets, MilpaCoreEngine, check_core_contract, import_core
from api.adapters.not_integrated import default_ports
from api.adapters.ports import Ports
from api.config import get_settings
from api.db.engine import get_engine


def _describe_zone(zone_id: UUID) -> ZoneSpec | None:
    """Datos públicos de la zona que necesita la ETL (nombre, centroide, elevación, polígono)."""
    engine = get_engine(get_settings().database_url)
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT name, ST_Y(ST_Centroid(geom)) AS lat, ST_X(ST_Centroid(geom)) AS lon, "
                    "elevation_m, ST_AsGeoJSON(ST_GeometryN(geom, 1), 5) AS gj "
                    "FROM geo.zone WHERE zone_id = :z"
                ),
                {"z": zone_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    return ZoneSpec(
        name=row["name"],
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        elevation_m=None if row["elevation_m"] is None else float(row["elevation_m"]),
        geojson=json.loads(row["gj"]),
    )


def load_ports() -> Ports:
    ports = default_ports()
    # La ingesta por proceso es opcional: solo entonces se leen los Settings completos.
    if os.environ.get("ETL_INGEST_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        settings = get_settings()
        etl = ProcessIngest(
            data_dir=settings.data_dir,
            describe_zone=_describe_zone,
            step_timeout_seconds=settings.etl_step_timeout_seconds,
            earthdata_token=settings.earthdata_token.get_secret_value()
            if settings.earthdata_token
            else None,
        )
        if etl.is_available():
            ports.ingest = etl
    core = import_core()
    if core is not None and check_core_contract(core).ok:
        ports.engine = MilpaCoreEngine(core, _core_assets())
    return ports


def _core_assets() -> CoreAssets | None:
    """Rutas de entrada del motor; ``None`` si el region pack/catálogos no existen (no se inventan)."""
    try:
        settings = get_settings()
    except Exception:  # sin configuración completa (p. ej. herramientas): motor sin entradas
        return None
    paths = (settings.core_region_path, settings.core_strategies_path, settings.core_catalogs_dir)
    if not all(p.exists() for p in paths):
        return None

    def daily_for_zone(zone_id: UUID) -> Path:
        spec = _describe_zone(zone_id)
        curated = settings.data_dir / "curated"
        for slug in ([spec.name] if spec else []) + [str(zone_id)]:
            candidate = curated / slug / "daily.parquet"
            if candidate.is_file():
                return candidate
        return curated / (spec.name if spec else str(zone_id)) / "daily.parquet"

    return CoreAssets(
        region_path=settings.core_region_path,
        strategies_path=settings.core_strategies_path,
        catalogs_dir=settings.core_catalogs_dir,
        daily_for_zone=daily_for_zone,
    )
