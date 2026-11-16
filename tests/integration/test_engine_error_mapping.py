"""Los errores tipados del motor (R2) llegan al cliente como códigos de dominio (DOBLE DE PRUEBA)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api.adapters.not_integrated import default_ports
from api.jobs.dispatch import NullDispatcher
from api.main import create_app
from testkit.app import World
from testkit.doubles import FakeEngine

RANK = {
    "scenario_id": "BASE",
    "weights": {"water": "0.25", "soil": "0.25", "food": "0.25", "income": "0.25"},
    "stability": {"n_samples": 10, "mode": "dirichlet", "concentration": 1.0, "seed": 1},
}


class RaisingEngine(FakeEngine):
    def __init__(self, exc: Exception) -> None:
        super().__init__()
        self.exc = exc

    def rank(self, run: Any, request: Any) -> Any:
        raise self.exc

    def heatmap(self, run: Any, params: Any) -> Any:
        raise self.exc


def client_with(engine: RaisingEngine, app_engine: Engine, settings: Any) -> TestClient:
    ports = default_ports()
    ports.engine = engine
    return TestClient(
        create_app(
            settings,
            engine=app_engine,
            ports=ports,
            dispatcher=NullDispatcher(),
            recover_on_start=False,
        ),
        raise_server_exceptions=False,
    )


def test_typed_engine_errors_become_422_with_spec_codes(
    app_engine: Engine, settings: Any, world: World
) -> None:
    run = world.f.run(world.zone, None, "ok")
    world.f.scenario(run)
    for cls_name, code in [
        ("MixedCycleLengthError", "MIXED_CYCLE_LENGTH"),
        ("NotComparable", "NOT_COMPARABLE"),
        ("MissingThresholdCitation", "MISSING_THRESHOLD_CITATION"),
        ("InsufficientSoilData", "INSUFFICIENT_SOIL_DATA"),
    ]:
        exc = type(cls_name, (Exception,), {})("detalle de dominio")
        with client_with(RaisingEngine(exc), app_engine, settings) as c:
            tok = c.post(
                "/v1/auth/login",
                json={"email": world.tech["email"], "password": world.tech["password"]},
            ).json()["access_token"]
            h = {"Authorization": f"Bearer {tok}"}
            r = c.post(f"/v1/runs/{run}/rank", json=RANK, headers=h)
            assert (
                r.status_code == 422
                and r.json()["code"] == code
                and "detalle de dominio" in r.json()["detail"]
            )
            g = c.get(f"/v1/runs/{run}/heatmap", params={"scenario": "BASE"}, headers=h)
            assert g.status_code == 422 and g.json()["code"] == code


def test_unknown_engine_exception_is_a_generic_500_without_details(
    app_engine: Engine, settings: Any, world: World
) -> None:
    run = world.f.run(world.zone, None, "ok")
    world.f.scenario(run)
    with client_with(
        RaisingEngine(RuntimeError("secreto interno persona@example.org")), app_engine, settings
    ) as c:
        tok = c.post(
            "/v1/auth/login",
            json={"email": world.tech["email"], "password": world.tech["password"]},
        ).json()["access_token"]
        r = c.post(f"/v1/runs/{run}/rank", json=RANK, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR"
    assert "secreto interno" not in r.text and "persona@example.org" not in r.text
