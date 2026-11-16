"""Endurecimiento hallado en revisión: GeoJSON mal formado y fallos del despachador de trabajos."""

from __future__ import annotations

from concurrent.futures.process import BrokenProcessPool
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.jobs.dispatch import ProcessPoolDispatcher, WorkerConfig
from api.main import create_app
from testkit.app import World

SQUARE = [[-89.55, 14.45], [-89.45, 14.45], [-89.45, 14.55], [-89.55, 14.55], [-89.55, 14.45]]


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": "x"},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]},  # anillo corto
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},  # no cerrado
        {
            "type": "Polygon",
            "coordinates": [[[999, 0], [1, 0], [1, 1], [999, 0]]],
        },  # fuera de rango
        {"type": "Polygon", "coordinates": [[["a", "b"], [1, 0], [1, 1], ["a", "b"]]]},
        {"type": "Polygon", "coordinates": [[[True, False], [1, 0], [1, 1], [True, False]]]},
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0]]]]},
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [SQUARE], "crs": {"type": "name"}},
        {"type": "Point", "coordinates": [0, 0]},
    ],
)
def test_malformed_geojson_is_a_422_never_a_500(
    client: TestClient, login: Any, world: World, geometry: dict[str, Any]
) -> None:
    r = client.post(
        "/v1/zones",
        headers=login(world.tech),
        json={"region_id": str(world.region), "name": "Z", "geometry": geometry},
    )
    assert r.status_code == 422, (geometry, r.status_code, r.text)
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_valid_geojson_polygon_and_multipolygon_are_accepted(
    client: TestClient, login: Any, world: World
) -> None:
    h = login(world.tech)
    for geom in (
        {"type": "Polygon", "coordinates": [SQUARE]},
        {"type": "MultiPolygon", "coordinates": [[SQUARE]]},
    ):
        r = client.post(
            "/v1/zones",
            headers=h,
            json={"region_id": str(world.region), "name": "Z", "geometry": geom},
        )
        assert r.status_code == 202, r.text


def test_unknown_region_and_postgis_rejection_do_not_500(
    client: TestClient, login: Any, world: World
) -> None:
    h = login(world.tech)
    body = {
        "region_id": str(uuid4()),
        "name": "Z",
        "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
    }
    assert client.post("/v1/zones", headers=h, json=body).status_code == 422


class ExplodingDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    def submit(self, job_id: Any) -> None:
        self.calls += 1
        raise RuntimeError("el pool no responde")

    def shutdown(self) -> None:
        return None


def test_dispatch_failure_keeps_job_queued_and_still_answers_202(
    app_engine: Engine, settings: Any, ports: Any, world: World, admin_engine: Engine
) -> None:
    d = ExplodingDispatcher()
    app = create_app(settings, engine=app_engine, ports=ports, dispatcher=d, recover_on_start=False)
    with TestClient(app) as c:
        tok = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_a_user["email"],
                "password": world.farmer_a_user["password"],
            },
        ).json()["access_token"]
        r = c.delete(f"/v1/parcels/{world.parcel_a}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 202 and r.json()["status"] == "queued" and d.calls == 1
    with (
        admin_engine.connect() as c2
    ):  # el trabajo está persistido: lo recuperará recover_jobs al reiniciar
        assert c2.execute(text("SELECT status::text FROM engine.job")).scalar_one() == "queued"


def test_broken_process_pool_is_recreated_once(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = WorkerConfig(
        database_url="postgresql+psycopg://x/y", data_dir=".", max_attempts=1, timeout_seconds=0
    )
    d = ProcessPoolDispatcher(cfg, max_workers=1)
    created: list[object] = []

    class BrokenThenGood:
        def __init__(self, broken: bool) -> None:
            self.broken = broken

        def submit(self, fn: Any, *a: Any) -> Any:
            if self.broken:
                raise BrokenProcessPool
            from concurrent.futures import Future

            fut: Future[None] = Future()
            fut.set_result(None)
            created.append(fn)
            return fut

        def shutdown(self, **kw: Any) -> None:
            return None

    pools = [BrokenThenGood(True), BrokenThenGood(False)]

    def fake_executor(self: ProcessPoolDispatcher) -> Any:
        if self._pool is None:
            self._pool = pools.pop(0)  # type: ignore[assignment]
        return self._pool

    monkeypatch.setattr(ProcessPoolDispatcher, "_executor", fake_executor)
    d.submit(uuid4())
    assert len(created) == 1 and not pools  # recreó el pool y envió el trabajo


@pytest.mark.parametrize("nul", ["a\u0000b", "\u0000", "x@y.org\u0000"])
def test_nul_characters_never_cause_a_500(
    client: TestClient, login: Any, world: World, nul: str
) -> None:
    """PostgreSQL no admite NUL en texto: debe ser un error de validación, no un 500 (hallado por Schemathesis)."""
    r = client.post("/v1/auth/login", json={"email": f"{nul}@example.org", "password": "x" * 12})
    assert r.status_code in (401, 422), r.text
    h = login(world.tech)
    z = client.post(
        "/v1/zones",
        headers=h,
        json={
            "region_id": str(world.region),
            "name": nul,
            "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
        },
    )
    assert z.status_code in (202, 422), z.text
    assert client.get("/v1/zones", params={"cursor": nul}, headers=h).status_code in (400, 422)
    p = client.get(f"/v1/parcels/{world.parcel_a}/soil", headers=h)
    assert p.status_code in (200, 404)
    prof = client.put(
        f"/v1/parcels/{world.parcel_a}/soil-declarations/{quote(nul)}",
        headers=h,
        json={"value": 6.0, "basis": nul},
    )
    assert prof.status_code in (404, 422), prof.text


# ------------------------------------------------- invariantes de seguridad al arrancar (S-01)
def test_service_refuses_to_start_if_a_view_can_bypass_rls(
    app_engine: Engine, admin_engine: Engine, settings: Any, dispatcher: Any, ports: Any
) -> None:
    """Un `CREATE OR REPLACE VIEW` sin security_invoker (p. ej. el script 92 de R1) evade RLS:
    el servicio debe negarse a arrancar en lugar de servir datos ajenos."""
    from api.db.invariants import SecurityInvariantViolation

    with admin_engine.connect() as c:
        c.execute(text("ALTER VIEW soil.property_status RESET (security_invoker)"))
    try:
        app = create_app(
            settings, engine=app_engine, ports=ports, dispatcher=dispatcher, recover_on_start=False
        )
        with pytest.raises(SecurityInvariantViolation) as exc, TestClient(app):
            pass
        assert "soil.property_status" in str(exc.value)
    finally:
        with admin_engine.connect() as c:
            c.execute(text("ALTER VIEW soil.property_status SET (security_invoker = true)"))
    app_ok = create_app(
        settings, engine=app_engine, ports=ports, dispatcher=dispatcher, recover_on_start=False
    )
    with TestClient(app_ok) as client:  # restaurada la invariante, arranca
        assert client.get("/healthz").status_code == 200
