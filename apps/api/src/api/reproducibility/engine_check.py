"""Huella reproducible de la corrida base del motor (``milpa_core``) sobre el paquete congelado.

``freeze`` recalcula la corrida BASE con la serie de ``data/demo/<zona>`` (SINTÉTICA, rotulada) y
guarda la huella en ``data/demo/EXPECTED_ENGINE.json``; ``verify`` la recalcula y la compara. La
huella cubre los hashes de entrada (datos, región, catálogos) y el resultado por ciclo redondeado a
``DECIMALS`` decimales (tolera ruido de último bit entre plataformas). No es una validación científica:
solo demuestra que el mismo código con los mismos datos da las mismas cifras.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.reproducibility.hashing import canonical_hash

DECIMALS = 6
EXPECTED_NAME = "EXPECTED_ENGINE.json"
REGION = Path("regions/r2/pilot_corredor_seco.yaml")
STRATEGIES = Path("regions/r2/pilot_corredor_seco.strategies.yaml")
CATALOGS = Path("catalogs/r2")


def fingerprint(demo_zone_dir: Path, root: Path) -> dict[str, Any]:
    from milpa_core import BASE, ENGINE_VERSION, make_context, run_analysis
    from milpa_core.enums import AdaptationMode

    from api.adapters import core_io

    region, extras = core_io.load_region(root / REGION)
    catalogs = core_io.load_catalogs(root / CATALOGS, mode=region.status)
    strategies = core_io.load_strategies(root / STRATEGIES)
    series, info = core_io.load_curated_daily(
        demo_zone_dir / "daily.parquet", extras.cell_id, region.window_start, region.window_end
    )
    ctx = make_context(
        region,
        catalogs,
        series,
        strategies,
        crops_enabled=extras.crops_enabled,
        ranking_cfg=extras.ranking_cfg,
        stability_cfg=extras.stability_cfg,
        voi_cfg=extras.voi_cfg,
        soil_cfg=extras.soil_cfg,
        seed=0,
        run_id="reproduce",
    )
    base = run_analysis(ctx, BASE, AdaptationMode.NONE)
    rows = [
        [
            r.strategy,
            r.cohort_year,
            r.cycle_idx,
            r.state.value,
            None if r.severity_mm is None else round(float(r.severity_mm), DECIMALS),
        ]
        for r in base.cycle_results
    ]
    return {
        "engine_version": ENGINE_VERSION,
        "label": "serie sintética rotulada (data/demo): no son observaciones reales",
        "zone": demo_zone_dir.name,
        "data_hash": ctx.data_hash,
        "region_config_hash": ctx.region_config_hash,
        "catalog_hash": ctx.catalogs.catalog_hash,
        "n_cycle_results": len(rows),
        "decimals": DECIMALS,
        "results_hash": canonical_hash({"rows": rows}),
        "missing_pct": info.missing_pct,
    }


def freeze(demo: Path, zone: str, root: Path) -> Path:
    out = demo / EXPECTED_NAME
    out.write_text(
        json.dumps(fingerprint(demo / zone, root), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def verify(demo: Path, zone: str, root: Path) -> tuple[list[str], str]:
    """Devuelve (diferencias, resumen). Lista vacía = reproducido."""
    path = demo / EXPECTED_NAME
    if not path.is_file():
        return [f"{path.name} ausente (ejecute `python -m api.cli freeze-engine`)"], ""
    expected = json.loads(path.read_text(encoding="utf-8"))
    now = fingerprint(demo / zone, root)
    keys = (
        "engine_version",
        "data_hash",
        "region_config_hash",
        "catalog_hash",
        "n_cycle_results",
        "results_hash",
    )
    diffs = [
        f"{k}: esperado {expected.get(k)!r}, obtenido {now[k]!r}"
        for k in keys
        if expected.get(k) != now[k]
    ]
    return (
        diffs,
        f"{now['n_cycle_results']} resultados por ciclo; results_hash {now['results_hash'][:12]}…",
    )
