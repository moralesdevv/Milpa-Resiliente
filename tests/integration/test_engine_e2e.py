"""De extremo a extremo con el motor REAL (milpa_core): API → trabajo → persistencia → lecturas.

Datos: serie SINTÉTICA ROTULADA de ``tools/r2/make_synthetic`` en un directorio temporal (prueba
aislada; no es evidencia ni se muestra en la app). El catálogo/región son los sandbox de R2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api import cli
from api.adapters.milpa_core import CoreAssets, MilpaCoreEngine, import_core
from api.adapters.not_integrated import default_ports
from api.jobs.dispatch import InlineDispatcher, WorkerConfig
from api.main import create_app
from testkit import ROOT
from testkit.app import World

pytestmark = pytest.mark.skipif(import_core() is None, reason="milpa_core no instalado")

BODY = {"period_start": "2021-01-01", "period_end": "2025-12-31", "seed": 7}
RANK = {
    "scenario_id": "T+1_P-10_D+0_Hrh",
    "adaptation_mode": "none",
    "weights": {"water": 0.25, "soil": 0.25, "food": 0.25, "income": 0.25},
    "stability": {"n_samples": 500, "mode": "dirichlet", "concentration": 10.0, "seed": 1},
}


@pytest.fixture
def e2e(
    app_engine: Engine,
    admin_engine: Engine,
    settings: Any,
    worker_config: WorkerConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    sys.path.insert(0, str(ROOT / "tools" / "r2"))
    try:
        from make_synthetic import make  # SINTÉTICO rotulado: solo esta prueba aislada
    finally:
        sys.path.pop(0)
    daily = tmp_path / "daily.csv"
    make("2021-01-01", "2025-12-31").to_csv(daily, index=False)
    core = import_core()
    assert core is not None
    assets = CoreAssets(
        ROOT / "regions" / "r2" / "pilot_corredor_seco.yaml",
        ROOT / "regions" / "r2" / "pilot_corredor_seco.strategies.yaml",
        ROOT / "catalogs" / "r2",
        lambda _zone: daily,
    )
    ports = default_ports()
    ports.engine = MilpaCoreEngine(core, assets)
    monkeypatch.setattr("api.jobs.handlers.engine_jobs.load_ports", lambda: ports)
    monkeypatch.setattr(cli, "_owner_engine", lambda: admin_engine)
    assert cli.cmd_register_engine(argparse.Namespace(catalogs=str(ROOT / "catalogs" / "r2"))) == 0
    app = create_app(
        settings,
        engine=app_engine,
        ports=ports,
        dispatcher=InlineDispatcher(worker_config),
        recover_on_start=False,
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _token(c: TestClient, user: dict[str, Any]) -> dict[str, str]:
    r = c.post("/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wait_job(c: TestClient, h: dict[str, str], job: dict[str, Any]) -> dict[str, Any]:
    r = c.get(f"/v1/jobs/{job['job_id']}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def test_register_engine_is_idempotent(e2e: TestClient, admin_engine: Engine) -> None:
    assert cli.cmd_register_engine(argparse.Namespace(catalogs=str(ROOT / "catalogs" / "r2"))) == 0
    with admin_engine.connect() as conn:
        n = conn.execute(text("SELECT count(*) FROM engine.scenario_def")).scalar_one()
    assert n == 45  # la grilla estándar de R2 ya incluye BASE


def test_base_run_scenarios_and_reads_use_the_real_engine(
    e2e: TestClient, world: World, admin_engine: Engine, data_dir: Path
) -> None:
    h = _token(e2e, world.tech)
    created = e2e.post(f"/v1/zones/{world.zone}/runs", json=BODY, headers={**h, "Idempotency-Key": "r1"})
    assert created.status_code in (200, 202), created.text
    job = _wait_job(e2e, h, created.json())
    assert job["status"] == "ok", job
    run_id = UUID(job["result"]["run_id"])

    run = e2e.get(f"/v1/runs/{run_id}", headers=h).json()
    assert run["status"] == "ok" and run["mode"] == "exposure" and run["sandbox"] is True
    assert len(run["data_hash"]) == 64 and run["code_version"].startswith("milpa_core")

    parquet = data_dir / "results" / str(run_id) / "BASE" / "none" / "cycle_result.parquet"
    assert parquet.is_file() and len(pd.read_parquet(parquet)) == job["result"]["base_cycle_rows"]

    summary = e2e.get(f"/v1/runs/{run_id}/summary", headers=h)
    assert summary.status_code == 200, summary.text
    assert summary.json()["strategies"]
    assert e2e.get(f"/v1/runs/{run_id}/heatmap", headers=h).status_code == 200
    assert e2e.get(f"/v1/runs/{run_id}/dekad-chart", headers=h).status_code == 200

    # un escenario no calculado sigue devolviendo 409 (nunca se calcula en una lectura)
    assert e2e.post(f"/v1/runs/{run_id}/rank", json=RANK, headers=h).status_code == 409
    sc = e2e.post(
        f"/v1/runs/{run_id}/scenarios",
        json={"scenario_ids": ["T+1_P-10_D+0_Hrh"], "adaptation_modes": ["none"]},
        headers={**h, "Idempotency-Key": "s1"},
    )
    assert sc.status_code in (200, 202), sc.text
    sjob = _wait_job(e2e, h, sc.json())
    assert sjob["status"] == "ok" and len(sjob["result"]["computed"]) == 1
    ranked = e2e.post(f"/v1/runs/{run_id}/rank", json=RANK, headers=h)
    assert ranked.status_code == 200, ranked.text
    assert ranked.json()["stability"]["seed"] == 1 and ranked.json()["ranking"]
    tags = e2e.get(f"/v1/runs/{run_id}/scenarios", headers=h).json()
    assert {t["scenario_id"] for t in tags} >= {"BASE", "T+1_P-10_D+0_Hrh"}
