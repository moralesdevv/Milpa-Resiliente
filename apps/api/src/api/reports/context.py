"""Contexto del informe que no viene del modelo del motor: cobertura de lluvia y escenarios calculados.

Solo LEE lo que R1/R2 ya produjeron (``coverage.parquet``, ``curated_meta.json``, escenarios persistidos).
Si algo no se puede leer, devuelve ``None``/lista vacía y el informe lo dice; nunca inventa cobertura.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from api.adapters.ports import EnginePort, RunRef
from api.errors import ApiError
from api.reports.from_engine import first_anchor_per_strategy
from api.repositories.analysis import RunRepository
from api.services.zones import curated_slug_for, read_json
from api.storage.object_store import ObjectStore
from api.storage.parquet import COVERAGE_CONTRACT, ParquetDatasetReader, curated_path

log = logging.getLogger("api.reports")
PRIMARY_RAIN_VARIABLE = "precip_imerg_mm"


def precip_coverage(
    store: ObjectStore, zone_id: UUID, zone_name: str
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    """Cobertura anual de la lluvia IMERG (días con dato / días del año) y ventana declarada por R1."""
    slug = curated_slug_for(store, zone_name, zone_id)
    meta = read_json(store, f"curated/{slug}/curated_meta.json")
    window = {
        "imerg_window": meta.get("imerg_window"),
        "fallback_days": meta.get("fallback_days"),
        "rain_primary": meta.get("precip_primary"),
    }
    try:
        df = ParquetDatasetReader(store).read(curated_path(slug, "coverage"), COVERAGE_CONTRACT)
    except ApiError as exc:  # dataset ausente o incompatible: el informe lo declara
        log.warning("report_coverage_unavailable", extra={"reason": exc.code})
        return None, window
    rows = df[df["variable"] == PRIMARY_RAIN_VARIABLE]
    if rows.empty:
        return None, window
    if "cell_id" in rows.columns:
        rows = rows[rows["cell_id"] == rows["cell_id"].min()]
    out = [
        {"year": int(r["year"]), "n_expected": int(r["n_expected"]), "n_valid": int(r["n_valid"])}
        for r in rows.sort_values("year").to_dict("records")
    ]
    return out, window


def computed_scenarios(
    engine: EnginePort, run: RunRef, runs: RunRepository, run_id: UUID, *, limit: int = 5
) -> list[Mapping[str, Any]]:
    """Escenarios sintéticos ya calculados (sin BASE), con su resumen de riesgo por estrategia."""
    out: list[Mapping[str, Any]] = []
    for tag in runs.scenario_tags(run_id):
        if tag["scenario_id"] == "BASE" or len(out) >= limit:
            continue
        summary = engine.summary(
            run, {"scenario": tag["scenario_id"], "adaptation": tag["adaptation_mode"]}
        )
        out.append(
            {
                "scenario": tag,
                "risk_rows": first_anchor_per_strategy(list(summary.get("strategies") or [])),
            }
        )
    return out
