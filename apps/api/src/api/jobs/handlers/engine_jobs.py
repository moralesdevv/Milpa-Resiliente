"""Handlers que dependen de R1/R2: ingesta de zona, corrida base y escenarios.

El cálculo lo hace ``milpa_core`` (vía ``EnginePort``); aquí solo se persiste lo que devuelve:
``engine.analysis_run`` / ``engine.scenario_run`` y la tabla ciclo-a-ciclo en Parquet (con su
SHA-256). Si el motor no está integrado el trabajo falla con ``DEPENDENCY_NOT_INTEGRATED``.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import text

from api.adapters.ports import RunRef
from api.adapters.registry import load_ports
from api.contracts.provisional_enums import AdaptationMode
from api.errors import DependencyNotIntegrated
from api.jobs.context import JobContext
from api.jobs.registry import register
from api.models.engine import AnalysisRun, ScenarioRun
from api.models.enums import JobKind
from api.reproducibility.hashing import canonical_hash, sha256_bytes


@register(JobKind.zone_ingest)
def zone_ingest(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    result = ports.ingest.ingest_zone(UUID(payload["zone_id"]))  # R1: DependencyNotIntegrated
    return {"v": 1, "ingest": dict(result)}


def _soil_snapshot(session: Any, parcel_id: UUID) -> list[dict[str, Any]]:
    """Estado por propiedad del suelo de la parcela, en JSON (la lectura respeta RLS)."""
    from api.repositories.farms import SoilRepository

    rows = SoilRepository(session).status_rows(parcel_id)
    snapshot: list[dict[str, Any]] = json.loads(json.dumps(rows, default=_json_default))
    return snapshot


def _json_default(value: Any) -> Any:
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return float(value)  # Decimal


def _results_path(run_id: UUID, scenario_id: str, adaptation: str) -> str:
    return f"results/{run_id}/{scenario_id}/{adaptation}/cycle_result.parquet"


def _persist_scenario(
    ctx: JobContext, run: RunRef, scenario_id: str, adaptation: str, engine_version: str
) -> int:
    """Escribe el Parquet del escenario y su fila ``engine.scenario_run``; devuelve n_rows."""
    ports = load_ports()
    rows = ports.engine.cycle_table(run, scenario_id, adaptation)
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_parquet(buffer, index=False)
    data = buffer.getvalue()
    relative = _results_path(run.run_id, scenario_id, adaptation)
    ctx.store.write_bytes(relative, data, overwrite=True)
    session = ctx.uow.session
    existing = session.get(ScenarioRun, (run.run_id, scenario_id, AdaptationMode(adaptation)))
    values = {
        "status": "ok",
        "results_uri": relative,
        "results_sha256": sha256_bytes(data),
        "n_rows": len(rows),
        "engine_version": engine_version,
        "executed_at": datetime.now(UTC),
    }
    if existing is None:
        session.add(
            ScenarioRun(
                run_id=run.run_id,
                scenario_id=scenario_id,
                adaptation_mode=AdaptationMode(adaptation),
                **values,
            )
        )
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    return len(rows)


@register(JobKind.analysis_run)
def analysis_run(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    session = ctx.uow.session
    parcel_id = UUID(str(payload["parcel_id"])) if payload.get("parcel_id") else None
    soil_rows = _soil_snapshot(session, parcel_id) if parcel_id else None
    outcome = ports.engine.run_base_analysis({**payload, "soil": soil_rows})
    info = outcome["run"]
    release_id = session.execute(
        text("SELECT catalog_release_id FROM ref.catalog_release WHERE catalog_hash = :h"),
        {"h": info["catalog_hash"]},
    ).scalar_one_or_none()
    if release_id is None:
        raise DependencyNotIntegrated(
            ports.engine.component,
            "El catálogo de R2 no está registrado en la base de datos "
            "(ejecute `python -m api.cli register-engine` con el rol propietario)",
        )
    period_start = date.fromisoformat(str(payload["period_start"]))
    period_end = date.fromisoformat(str(payload["period_end"]))
    params = {
        "seed": payload["seed"],
        "params": payload.get("params") or {},
        "period": [str(period_start), str(period_end)],
        "sandbox": info["sandbox"],
    }
    if soil_rows is not None:
        params["soil"] = soil_rows  # instantánea: permite reconstruir la corrida en otro proceso
    run_id = uuid4()
    session.add(
        AnalysisRun(
            run_id=run_id,
            zone_id=UUID(str(payload["zone_id"])),
            parcel_id=parcel_id,
            period_start=period_start,
            period_end=period_end,
            mode=info["mode"],
            mode_reasons=list(info["mode_reasons"]),
            params=params,
            params_hash=canonical_hash(params),
            region_config_hash=info["region_config_hash"],
            catalog_release_id=release_id,
            data_hash=info["data_hash"],
            code_version=info["code_version"],
            seed=int(payload["seed"]),
            created_by=ctx.created_by,
            status="ok",
        )
    )
    session.flush()
    ref = RunRef(
        run_id,
        UUID(str(payload["zone_id"])),
        parcel_id,
        info["data_hash"],
        canonical_hash(params),
        info["region_config_hash"],
        info["code_version"],
        int(payload["seed"]),
        period_start,
        period_end,
        params,
    )
    n_rows = _persist_scenario(ctx, ref, "BASE", "none", info["code_version"])
    ctx.uow.commit()
    return {
        "v": 1,
        "run_id": str(run_id),
        "mode": info["mode"],
        "sandbox": info["sandbox"],
        "base_cycle_rows": n_rows,
    }


@register(JobKind.scenario_run)
def scenario_run(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    ports = load_ports()
    from api.services.runs import run_ref_from_db

    run = run_ref_from_db(ctx.uow.session, UUID(payload["run_id"]))
    outcome = ports.engine.run_scenarios(run, payload)
    version = str(outcome["engine_version"])
    done: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    entries = list(outcome["scenarios"])
    for i, entry in enumerate(entries):
        ctx.check_cancelled()
        if entry["status"] == "ok":
            n_rows = _persist_scenario(
                ctx, run, entry["scenario_id"], entry["adaptation_mode"], version
            )
            done.append({**entry, "n_rows": n_rows})
        else:
            skipped.append(entry)  # no aplicable: se informa el motivo, no se inventa resultado
        ctx.progress((i + 1) / max(len(entries), 1))
    ctx.uow.commit()
    return {"v": 1, "run_id": str(run.run_id), "computed": done, "skipped": skipped}
