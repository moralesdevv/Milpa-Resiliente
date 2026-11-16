"""Contexto agrícola de una zona (cultivos, temporadas y decisiones pendientes) desde el region pack de R2.

Solo lee y resume lo que ya declaran ``regions/r2`` y ``catalogs/r2``: no define calendarios ni cultivos.
Cada cifra de «pendiente» sale de contar campos reales sin cita (nunca de un texto fijo).
"""

from __future__ import annotations

from typing import Any

from api.adapters import core_io
from api.config import Settings

# Nombres para mostrar (el catálogo de R2 solo trae el nombre en español).
_NAME_EN = {"maiz": "Maize", "frijol": "Common bean", "sorgo": "Sorghum"}


def agri_context(settings: Settings) -> dict[str, Any] | None:
    paths = (settings.core_region_path, settings.core_strategies_path, settings.core_catalogs_dir)
    if not all(p.exists() for p in paths):
        return None
    region, extras = core_io.load_region(settings.core_region_path)
    catalogs = core_io.load_catalogs(settings.core_catalogs_dir, mode=region.status)
    strategies = core_io.load_strategies(settings.core_strategies_path)

    seasons_by_crop: dict[str, set[str]] = {}
    for strategy in strategies:
        for cycle in strategy.cycles:
            for comp in cycle.components:
                crop = catalogs.varieties[comp.variety].crop
                seasons_by_crop.setdefault(crop, set()).add(cycle.season)
    enabled = list(extras.crops_enabled or catalogs.crops)
    crops = [
        {
            "code": code,
            "name_es": catalogs.crops[code].name_es,
            "name_en": _NAME_EN.get(code, catalogs.crops[code].name_es),
            "seasons": sorted(seasons_by_crop.get(code, set())),
            "calendar_validated": False,  # ningún calendario del paquete tiene cita (sandbox)
        }
        for code in enabled
        if code in catalogs.crops
    ]
    stages = [s for v in catalogs.varieties.values() for s in v.stages]
    pending: list[str] = []
    if region.status == "sandbox":
        pending.append(
            "Planting windows, start of the agricultural year and the candidate-date step are sandbox values"
        )
    for field in region.pending_fields():
        pending.append(
            {
                "onset": "Rain-onset definition has no citation (delay scenarios are enabled for sandbox only)",
                "adaptation": "Adaptation lag has no citation",
                "phi": "Fixed-fraction effective-rain coefficient has no citation",
            }[field]
        )
    uncited_stages = sum(1 for s in stages if not s.citation)
    uncited_thr = sum(1 for t in catalogs.thresholds if not t.citation)
    pending.append(f"{uncited_stages} of {len(stages)} crop stages have no cited Kc/length")
    pending.append(
        f"{uncited_thr} of {len(catalogs.thresholds)} critical thresholds have no citation (results stay provisional)"
    )
    return {
        "status": region.status,
        "region": region.code,
        "seasons": [
            {
                "code": code,
                "plant_window": list(season.plant_window),
                "calendar_year_shift": season.calendar_year_shift,
            }
            for code, season in region.seasons.items()
        ],
        "crops": crops,
        "pending": pending,
        "source": "regions/r2 region pack and catalogs/r2 (R2 sandbox)",
    }
