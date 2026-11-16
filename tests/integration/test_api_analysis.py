"""Endpoints de análisis (BE-06), zonas/calidad de datos (R1), catálogo, informes y procedencia.

Las filas de corridas/escenarios son FILAS DE PRUEBA que representan "una corrida existe"; no
contienen ni simulan resultados científicos. El motor es un doble de prueba o el puerto no integrado.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api.adapters.not_integrated import default_ports
from api.main import create_app
from testkit.app import World
from testkit.doubles import FakeEngine

WEIGHTS = {"water": "0.25", "soil": "0.25", "food": "0.25", "income": "0.25"}
RANK = {
    "scenario_id": "BASE",
    "adaptation_mode": "none",
    "weights": WEIGHTS,
    "stability": {"n_samples": 100, "mode": "dirichlet", "concentration": 10.0, "seed": 1},
}


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def engine_client(
    app_engine: Engine, settings: Any, dispatcher: Any, fake_engine: FakeEngine
) -> Any:
    ports = default_ports()
    ports.engine = fake_engine  # DOBLE DE PRUEBA de R2
    with TestClient(
        create_app(
            settings, engine=app_engine, ports=ports, dispatcher=dispatcher, recover_on_start=False
        )
    ) as c:
        yield c


def hdr(client: TestClient, user: dict[str, Any]) -> dict[str, str]:
    t = client.post(
        "/v1/auth/login", json={"email": user["email"], "password": user["password"]}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


# ----------------------------------------------------------------------- sin R2: error claro
READS = ["climate-history", "summary", "heatmap", "dekad-chart"]


@pytest.mark.parametrize("path", READS)
def test_read_endpoints_return_503_not_integrated_never_fake_data(
    client: TestClient, login: Any, world: World, path: str
) -> None:
    run = world.f.run(world.zone, None, "ok")
    r = client.get(f"/v1/runs/{run}/{path}", headers=login(world.tech))
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_NOT_INTEGRATED"
    assert "R2" in r.json()["detail"] and r.json()["hint"]


def test_rank_and_voi_return_503_not_integrated_when_computed(
    client: TestClient, login: Any, world: World
) -> None:
    run = world.f.run(world.zone, world.parcel_a, "ok")
    world.f.scenario(run, "BASE", "none")
    h = login(world.farmer_a_user)
    assert (
        client.post(f"/v1/runs/{run}/rank", json=RANK, headers=h).json()["code"]
        == "DEPENDENCY_NOT_INTEGRATED"
    )
    voi = client.post(f"/v1/runs/{run}/soil-voi", json={"scenario_id": "BASE"}, headers=h)
    assert voi.status_code == 503 and voi.json()["code"] == "DEPENDENCY_NOT_INTEGRATED"


# ----------------------------------------------------------------------- reglas de estado
def test_scenario_not_computed_returns_409_and_never_calls_engine(
    engine_client: TestClient, world: World, fake_engine: FakeEngine
) -> None:
    run = world.f.run(world.zone, None, "ok")
    h = hdr(engine_client, world.tech)
    r = engine_client.get(
        f"/v1/runs/{run}/summary", params={"scenario": "T+2_P-20_D+20_Hrh"}, headers=h
    )
    assert r.status_code == 409 and r.json()["code"] == "SCENARIO_NOT_COMPUTED"
    assert f"/v1/runs/{run}/scenarios" in r.json()["hint"]  # enlace al trabajo que lo calcula
    rk = engine_client.post(
        f"/v1/runs/{run}/rank", json={**RANK, "scenario_id": "T+2_P-20_D+20_Hna"}, headers=h
    )
    assert rk.status_code == 409 and rk.json()["code"] == "SCENARIO_NOT_COMPUTED"
    assert fake_engine.calls == []  # nunca se calcula en silencio dentro de una lectura


def test_computed_scenario_passes_through_to_engine_port(
    engine_client: TestClient, world: World, fake_engine: FakeEngine
) -> None:
    run = world.f.run(world.zone, None, "ok")
    world.f.scenario(run, "BASE", "none")
    h = hdr(engine_client, world.tech)
    r = engine_client.get(
        f"/v1/runs/{run}/summary", params={"scenario": "BASE", "adaptation": "none"}, headers=h
    )
    assert r.status_code == 200 and r.json() == {"test_double": True, "method": "summary"}
    rk = engine_client.post(f"/v1/runs/{run}/rank", json=RANK, headers=h)
    assert rk.status_code == 200 and fake_engine.calls[-1][0] == "rank"
    assert fake_engine.calls[-1][1]["weights"]["water"] == 0.25


def test_run_not_ready_is_409(client: TestClient, login: Any, world: World) -> None:
    run = world.f.run(world.zone, None, "running")
    r = client.get(f"/v1/runs/{run}/summary", headers=login(world.tech))
    assert r.status_code == 409 and r.json()["code"] == "RUN_NOT_READY"


def test_rank_request_validation(engine_client: TestClient, world: World) -> None:
    run = world.f.run(world.zone, None, "ok")
    world.f.scenario(run)
    h = hdr(engine_client, world.tech)
    bad = [
        {**RANK, "weights": {**WEIGHTS, "income": "0.5"}},  # no suman 1
        {**RANK, "scenario_id": "inventado"},  # id de escenario inválido
        {**RANK, "stability": {**RANK["stability"], "n_samples": 10**9}},  # tope de seguridad
        {**RANK, "missing_policy": "otra"},
        {**RANK, "extra": 1},
        {**RANK, "adaptation_mode": "magia"},
    ]
    for payload in bad:
        assert (
            engine_client.post(f"/v1/runs/{run}/rank", json=payload, headers=h).status_code == 422
        ), payload


# ----------------------------------------------------------------------- autorización por pertenencia
def test_run_authorization_follows_parcel_ownership(
    client: TestClient, login: Any, world: World
) -> None:
    private_run = world.f.run(world.zone, world.parcel_a, "ok")
    zone_run = world.f.run(world.zone, None, "ok")
    for user, expected in [
        (world.farmer_a_user, 200),
        (world.tech, 200),
        (world.farmer_b_user, 404),
        (world.tech_unassigned, 404),
        (world.admin, 404),
    ]:
        assert client.get(f"/v1/runs/{private_run}", headers=login(user)).status_code == expected, (
            user["role"]
        )
    for user in (world.farmer_a_user, world.farmer_b_user, world.tech_unassigned, world.admin):
        assert (
            client.get(f"/v1/runs/{zone_run}", headers=login(user)).status_code == 200
        )  # contexto de zona
    assert client.get(f"/v1/runs/{private_run}").status_code == 401
    assert client.get(f"/v1/runs/{uuid4()}", headers=login(world.tech)).status_code == 404


def test_run_detail_includes_hashes_and_supports_etag(
    client: TestClient, login: Any, world: World
) -> None:
    run = world.f.run(world.zone, None, "ok")
    h = login(world.tech)
    r = client.get(f"/v1/runs/{run}", headers=h)
    body = r.json()
    assert r.status_code == 200 and body["data_hash"] == "d" * 64 and body["seed"] == 42
    assert body["code_version"] == "test-code-version" and "etag" in {k.lower() for k in r.headers}
    again = client.get(f"/v1/runs/{run}", headers={**h, "If-None-Match": r.headers["ETag"]})
    assert again.status_code == 304
    world.f._exec("UPDATE engine.analysis_run SET data_hash=:h WHERE run_id=:r", h="f" * 64, r=run)
    changed = client.get(f"/v1/runs/{run}", headers={**h, "If-None-Match": r.headers["ETag"]})
    assert (
        changed.status_code == 200 and changed.headers["ETag"] != r.headers["ETag"]
    )  # cambia con el data_hash


def test_scenarios_listing_hides_internal_paths(
    client: TestClient, login: Any, world: World
) -> None:
    run = world.f.run(world.zone, None, "ok")
    world.f.scenario(run, "BASE", "none")
    r = client.get(f"/v1/runs/{run}/scenarios", headers=login(world.tech))
    assert r.status_code == 200
    s = r.json()[0]  # ScenarioTag[] (README §15)
    assert s["scenario_id"] == "BASE" and "results_uri" not in s and "test://uri" not in r.text
    assert s["label"] == "escenario sintético" and s["humidity_assumption"] == "not_applicable"
    assert {
        "delta_t_c",
        "precip_factor",
        "onset_delay_days",
        "adaptation_mode",
        "method_doc",
    } <= set(s)


def test_job_creating_endpoints_require_technician_or_admin(
    client: TestClient, login: Any, world: World
) -> None:
    run = world.f.run(world.zone, None, "ok")
    assert (
        client.post(
            f"/v1/runs/{run}/scenarios", json={}, headers=login(world.farmer_a_user)
        ).status_code
        == 403
    )
    ok = client.post(
        f"/v1/runs/{run}/scenarios", json={"scenario_ids": ["BASE"]}, headers=login(world.tech)
    )
    assert (
        ok.status_code == 202
        and ok.json()["kind"] == "scenario_run"
        and ok.json()["status"] == "queued"
    )
    base = {
        "period_start": "2001-01-01",
        "period_end": "2025-12-31",
        "seed": 7,
        "params": {"peff_method": "x"},
    }
    assert (
        client.post(
            f"/v1/zones/{world.zone}/runs", json=base, headers=login(world.farmer_a_user)
        ).status_code
        == 403
    )
    r = client.post(f"/v1/zones/{world.zone}/runs", json=base, headers=login(world.tech))
    assert r.status_code == 202 and r.headers["Location"].startswith("/v1/jobs/")
    foreign = {**base, "parcel_id": str(world.parcel_b)}
    assert (
        client.post(
            f"/v1/zones/{world.zone}/runs", json=foreign, headers=login(world.tech)
        ).status_code
        == 404
    )
    assert (
        client.post(f"/v1/zones/{uuid4()}/runs", json=base, headers=login(world.tech)).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/zones/{world.zone}/runs",
            json={**base, "period_end": "2000-01-01"},
            headers=login(world.tech),
        ).status_code
        == 422
    )


# ----------------------------------------------------------------------- zonas y calidad de datos (R1)
def write_coverage(
    data_dir: Path, zone: Any, rows: list[dict[str, Any]] | None = None, drop: str | None = None
) -> Path:
    # ARCHIVO SINTÉTICO DE PRUEBA con las columnas propuestas en README §13.7 (no son datos reales)
    rows = (
        rows
        if rows is not None
        else [
            {
                "cell_id": c,
                "variable": v,
                "year": y,
                "n_expected": 365,
                "n_valid": 360,
                "pct_missing": 1.37,
            }
            for c in (1, 2)
            for v in ("precip_mm", "tmax_c")
            for y in (2001, 2002)
        ]
    )
    df = pd.DataFrame(rows)
    if drop:
        df = df.drop(columns=[drop])
    path = data_dir / "curated" / str(zone) / "coverage.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def test_zones_listing_pagination_and_detail(client: TestClient, login: Any, world: World) -> None:
    for i in range(4):
        world.f._exec(
            "INSERT INTO geo.zone (region_id, name, geom) VALUES (:r, :n, ST_Multi(ST_GeomFromText('POLYGON((-89.6 14.4,-89.5 14.4,-89.5 14.5,-89.6 14.4))',4326)))",
            r=world.region,
            n=f"Zona {i}",
        )
    h = login(world.farmer_b_user)
    page1 = client.get("/v1/zones", params={"limit": 2}, headers=h).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    seen = {z["zone_id"] for z in page1["items"]}
    page2 = client.get(
        "/v1/zones", params={"limit": 2, "cursor": page1["next_cursor"]}, headers=h
    ).json()
    assert not seen & {z["zone_id"] for z in page2["items"]}
    assert (
        client.get("/v1/zones", params={"cursor": "%%%no-es-cursor"}, headers=h).json()["code"]
        == "INVALID_CURSOR"
    )
    huge = client.get("/v1/zones", params={"limit": 100000}, headers=h)
    assert huge.status_code == 200 and len(huge.json()["items"]) <= 100
    detail = client.get(f"/v1/zones/{world.zone}", headers=h).json()
    assert detail["geometry"]["type"] == "MultiPolygon" and detail["soil_estimates"] == []
    assert client.get(f"/v1/zones/{uuid4()}", headers=h).status_code == 404


def test_data_quality_unavailable_incompatible_and_ok(
    client: TestClient, login: Any, world: World, data_dir: Path
) -> None:
    h = login(world.tech)
    url = f"/v1/zones/{world.zone}/data-quality"
    missing = client.get(url, headers=h)
    assert missing.status_code == 503 and missing.json()["code"] == "DATASET_UNAVAILABLE"
    assert str(data_dir) not in missing.text  # no revela rutas internas
    write_coverage(data_dir, world.zone, drop="n_valid")
    bad = client.get(url, headers=h)
    assert (
        bad.status_code == 503
        and bad.json()["code"] == "DATASET_INCOMPATIBLE"
        and "n_valid" in bad.json()["detail"]
    )
    path = write_coverage(data_dir, world.zone)
    ok = client.get(url, params={"limit": 3}, headers=h).json()
    assert ok["dataset"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert ok["dataset"]["contract_status"] == "confirmed_by_delivered_files"
    assert len(ok["coverage"]) == 3 and ok["next_cursor"]
    assert ok["comparisons"] == [] and ok["sources"] == [] and ok["ea_sensitivity_mm_day"] is None
    only = client.get(url, params={"variable": "tmax_c", "year": 2002}, headers=h).json()
    assert {(r["variable"], r["year"]) for r in only["coverage"]} == {("tmax_c", 2002)}
    path.write_bytes(b"no es parquet")
    corrupt = client.get(url, headers=h)
    assert corrupt.status_code == 503 and corrupt.json()["code"] == "DATASET_INCOMPATIBLE"


# ----------------------------------------------------------------------- catálogos de R1
def test_catalog_endpoints_empty_then_populated(
    client: TestClient, login: Any, world: World
) -> None:
    h = login(world.farmer_a_user)
    for p in ("crops", "strategies", "references"):
        assert client.get(f"/v1/catalog/{p}", headers=h).json() == {
            "items": [],
            "next_cursor": None,
        }
    f = world.f
    f._exec(
        "INSERT INTO ref.crop (code, name_es, name_en, family) VALUES ('maize','Maíz','Maize','Poaceae')"
    )
    sid = f._one(
        "INSERT INTO ref.strategy (code, name, is_reference) VALUES ('REF','Referencia',true) RETURNING strategy_id"
    )
    rel = f._one(
        "INSERT INTO ref.catalog_release (catalog_hash, git_sha) VALUES (repeat('9',64),'t') RETURNING catalog_release_id"
    )
    f._exec(
        "INSERT INTO ref.strategy_version (strategy_id, version, catalog_release_id, horizon_years) VALUES (:s,1,:r,1)",
        s=sid,
        r=rel,
    )
    f._exec("INSERT INTO prov.citation (bibkey, full_text) VALUES ('fao56','Allen et al. 1998')")
    assert client.get("/v1/catalog/crops", headers=h).json()["items"][0]["code"] == "maize"
    assert (
        client.get("/v1/catalog/strategies", headers=h).json()["items"][0]["is_reference"] is True
    )
    assert client.get("/v1/catalog/references", headers=h).json()["items"][0]["bibkey"] == "fao56"
    v = client.get(f"/v1/catalog/strategies/{sid}/versions/1", headers=h)
    assert v.status_code == 200 and v.json()["version"] == 1 and v.json()["cycles"] == []
    assert client.get(f"/v1/catalog/strategies/{sid}/versions/9", headers=h).status_code == 404
    assert client.get("/v1/catalog/crops").status_code == 401


# ----------------------------------------------------------------------- informes (acceso e integridad)
def seed_report(
    world: World, data_dir: Path, owner: dict[str, Any], content: bytes = b"%PDF-1.7 prueba"
) -> tuple[Any, Path]:
    rel = "reports/informe-prueba.pdf"
    (data_dir / "reports").mkdir(exist_ok=True)
    pdf = data_dir / rel
    pdf.write_bytes(content)
    rid = world.f._one(
        "INSERT INTO report.report (privacy_level, content_json, pdf_uri, pdf_sha256, generated_by, template_version, locale) "
        "VALUES ('internal', CAST(:c AS jsonb), :u, :h, :g, 'provisional-technical-v0', 'es') RETURNING report_id",
        c='{"sections":[{"title_es":"t"}],"annex":[]}',
        u=rel,
        h=hashlib.sha256(content).hexdigest(),
        g=owner["user_id"],
    )
    return rid, pdf


def test_report_download_verifies_hash_and_access(
    client: TestClient, login: Any, world: World, data_dir: Path
) -> None:
    rid, pdf = seed_report(world, data_dir, world.tech)
    h = login(world.tech)
    meta = client.get(f"/v1/reports/{rid}", headers=h).json()
    assert (
        meta["pdf_url"] == f"/v1/reports/{rid}/pdf"
        and meta["template_version"] == "provisional-technical-v0"
    )
    ok = client.get(f"/v1/reports/{rid}/pdf", headers=h)
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
    assert ok.headers["X-Content-SHA256"] == hashlib.sha256(b"%PDF-1.7 prueba").hexdigest()
    assert (
        client.get(f"/v1/reports/{rid}/pdf", headers=login(world.farmer_b_user)).status_code == 404
    )
    assert client.get(f"/v1/reports/{rid}", headers=login(world.admin)).status_code == 404
    pdf.write_bytes(b"%PDF-1.7 ALTERADO")
    bad = client.get(f"/v1/reports/{rid}/pdf", headers=h)
    assert bad.status_code == 500 and bad.json()["code"] == "INTEGRITY_CHECK_FAILED"
    assert str(data_dir) not in bad.text
    pdf.unlink()
    assert client.get(f"/v1/reports/{rid}/pdf", headers=h).status_code == 404


def test_report_request_checks_access_and_consents(
    client: TestClient, login: Any, world: World
) -> None:
    run = world.f.run(world.zone, world.parcel_a, "ok")
    body = {"run_id": str(run), "locale": "es", "privacy_level": "internal"}
    r = client.post("/v1/reports", json=body, headers=login(world.tech))
    assert r.status_code == 202 and r.json()["kind"] == "report"
    assert (
        client.post("/v1/reports", json=body, headers=login(world.farmer_b_user)).status_code == 404
    )
    public = client.post(
        "/v1/reports", json={**body, "privacy_level": "public"}, headers=login(world.tech)
    )
    assert (
        public.status_code == 403 and public.json()["code"] == "CONSENT_REQUIRED"
    )  # sin 'report_sharing'
    world.f.consent(world.farmer_a_user, "report_sharing")
    assert (
        client.post(
            "/v1/reports", json={**body, "privacy_level": "public"}, headers=login(world.tech)
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/v1/reports", json={**body, "locale": "fr"}, headers=login(world.tech)
        ).status_code
        == 422
    )


def test_provenance_zone_level_is_public_to_authenticated_but_parcel_level_is_not(
    client: TestClient, login: Any, world: World
) -> None:
    pub = world.f._one(
        "INSERT INTO prov.indicator_provenance (indicator_code, unit, provenance, evidence_level, source_ids, processing_method, evidence_rule_id) "
        "VALUES ('x','u','satelital','B','{}','m','r') RETURNING ip_id"
    )
    world.f.soil_property("ph")
    priv = world.f.sample_with_measurement(world.parcel_a)
    for user in (world.farmer_b_user, world.tech_unassigned):
        assert client.get(f"/v1/provenance/{pub}", headers=login(user)).status_code == 200
        assert client.get(f"/v1/provenance/{priv}", headers=login(user)).status_code == 404
    assert client.get(f"/v1/provenance/{priv}", headers=login(world.tech)).status_code == 200
    assert client.get(f"/v1/provenance/{pub}").status_code == 401
    assert client.get(f"/v1/provenance/{uuid4()}", headers=login(world.tech)).status_code == 404


def test_every_v1_route_requires_authentication(client: TestClient) -> None:
    """RBAC: ninguna ruta de /v1 salvo login es accesible sin token."""
    open_routes = {("POST", "/v1/auth/login"), ("POST", "/v1/auth/demo-session")}
    schema = client.get("/openapi.json").json()
    checked = 0
    for path, ops in schema["paths"].items():
        if not path.startswith("/v1"):
            continue
        for method in ops:
            if (method.upper(), path) in open_routes:
                continue
            concrete = re.sub(r"\{(version|property_code)\}", "1", path)
            concrete = re.sub(r"\{[a-z_]+\}", lambda _m: str(uuid4()), concrete)
            r = client.request(method.upper(), concrete, json={} if method != "get" else None)
            assert r.status_code == 401, (method, path, r.status_code)
            checked += 1
    assert checked >= 28


def test_catalog_lists_are_paginated_by_cursor(
    client: TestClient, login: Any, world: World
) -> None:
    for i in range(5):
        world.f._exec(
            "INSERT INTO ref.crop (code, name_es, name_en, family) VALUES (:c, 'n', 'n', 'f')",
            c=f"crop{i}",
        )
    h = login(world.farmer_a_user)
    seen: list[str] = []
    cursor = None
    for _ in range(5):
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/v1/catalog/crops", params=params, headers=h).json()
        seen += [c["code"] for c in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"crop{i}" for i in range(5)]
    bad = client.get("/v1/catalog/crops", params={"cursor": "%%%"}, headers=h)
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_CURSOR"


def test_provenance_has_the_shape_of_the_spec_provenance_info(
    client: TestClient, login: Any, world: World
) -> None:
    """README §15 `ProvenanceInfo`: evidence, evidence_rule, sources[], period, spatial_res, …"""
    sid = world.f._one(
        "INSERT INTO prov.data_source (source_id, code, product_name, institution, is_nasa, "
        "version, access_url, temporal_res) VALUES (901, 'TEST_SRC', 'Producto de prueba', "
        "'Institución de prueba', true, '07', 'https://example.org/x', interval '1 day') "
        "RETURNING source_id"
    )
    ip = world.f._one(
        "INSERT INTO prov.indicator_provenance (indicator_code, unit, provenance, evidence_level, "
        "source_ids, processing_method, evidence_rule_id, period_start, period_end, "
        "spatial_res_m, temporal_res, dataset_version, missing_pct, assumptions, limitations) "
        "VALUES ('precip_mm','mm','satelital','C', ARRAY[901::smallint], 'FAO56-PM; prueba', "
        "'regla-de-prueba', '2001-01-01', '2025-12-31', 10000, interval '1 day', '07', 1.5, "
        "ARRAY['supuesto'], ARRAY['limitación']) RETURNING ip_id"
    )
    assert sid == 901
    body = client.get(f"/v1/provenance/{ip}", headers=login(world.tech)).json()
    assert body["provenance"] == "satelital" and body["evidence"] == "C"
    assert body["evidence_rule"] == "regla-de-prueba" and body["method"] == "FAO56-PM; prueba"
    assert body["period"] == {"start": "2001-01-01", "end": "2025-12-31"}
    assert body["spatial_res"] == "10000 m" and body["temporal_res"] == "P1D"
    assert body["dataset_version"] == "07" and body["missing_pct"] == 1.5
    assert body["assumptions"] == ["supuesto"] and body["limitations"] == ["limitación"]
    src = body["sources"][0]
    assert {"code", "product_name", "institution", "is_nasa", "version", "url", "citation"} <= set(
        src
    )
    assert src["is_nasa"] is True and src["code"] == "TEST_SRC"
    # nombres de columnas de la BD que NO son parte del DTO de la especificación
    assert not {"evidence_level", "evidence_rule_id", "processing_method", "spatial_res_m"} & set(
        body
    )


# ----------------------------------------------------------- datos REALES entregados por R1
R1_DATA = Path(__file__).resolve().parents[2] / "data" / "curated" / "chiquimula_prueba"


@pytest.mark.skipif(not R1_DATA.is_dir(), reason="data/curated/chiquimula_prueba (R1) no existe")
def test_zone_quality_and_detail_serve_the_real_r1_delivery(
    client: TestClient, login: Any, world: World, data_dir: Path
) -> None:
    """Integración R1→R3 con los archivos reales: nombre de zona = directorio curado, serie zonal."""
    import shutil

    f = world.f
    for sid, code, prod, inst, nasa in (
        (1, "POWER_DAILY", "NASA POWER diario", "NASA", True),
        (2, "IMERG_FINAL_V07", "GPM IMERG Final Run diario", "NASA GES DISC", True),
    ):
        f._exec(
            "INSERT INTO prov.data_source (source_id, code, product_name, institution, is_nasa) "
            "VALUES (:i,:c,:p,:n,:a)",
            i=sid,
            c=code,
            p=prod,
            n=inst,
            a=nasa,
        )
    zone = f._one(
        "INSERT INTO geo.zone (region_id, name, geom) VALUES (:r, 'chiquimula_prueba', "
        "ST_Multi(ST_GeomFromText('POLYGON((-89.6 14.4,-89.5 14.4,-89.5 14.5,-89.6 14.4))',4326))) "
        "RETURNING zone_id",
        r=world.region,
    )
    cell = f._one(
        "INSERT INTO geo.climate_cell (source_id, centroid, footprint) VALUES (1, "
        "ST_SetSRID(ST_MakePoint(-89.5, 14.8), 4326), ST_MakeEnvelope(-89.75, 14.55, -89.25, 15.05, 4326)) "
        "RETURNING cell_id"
    )
    f._exec(
        "INSERT INTO geo.zone_cell (zone_id, cell_id, weight) VALUES (:z,:c,1.0)", z=zone, c=cell
    )
    shutil.copytree(R1_DATA, data_dir / "curated" / "chiquimula_prueba")
    h = login(world.tech)

    q = client.get(f"/v1/zones/{zone}/data-quality", params={"limit": 50}, headers=h).json()
    assert (
        q["dataset"]["n_rows"] == 200
        and q["dataset"]["contract_status"] == "confirmed_by_delivered_files"
    )
    tmax = client.get(
        f"/v1/zones/{zone}/data-quality", params={"variable": "tmax_c", "year": 2001}, headers=h
    ).json()["coverage"]
    assert len(tmax) == 1 and tmax[0]["n_expected"] == 365
    assert all(r["cell_id"] is None for r in q["coverage"])  # serie por zona
    assert {s["code"] for s in q["sources"]} == {"IMERG_FINAL_V07", "POWER_DAILY"}
    cmp_ = q["comparisons"][0]
    assert cmp_["pair"] == "IMERG_FINAL_V07 vs POWER_DAILY" and cmp_["n_days_common"] == 1734
    assert cmp_["correlation_daily"] == 0.124 and cmp_["bias_mm_day"] == -0.968
    assert cmp_["ratio_total"] == 0.813 and cmp_["annual_ratio"]["2024"] == 1.003
    assert "NO es validar" in cmp_["note"]
    assert q["ea_sensitivity_mm_day"] == 0.149
    assert any("evidencia" in x or "UTC" in x for x in q["limitations"])

    d = client.get(f"/v1/zones/{zone}", headers=h).json()
    assert d["cells"][0]["weight"] == 1.0 and d["cells"][0]["source"] == "POWER_DAILY"
    assert d["cells"][0]["south"] < d["cells"][0]["north"]
    assert {s["code"] for s in d["sources"]} >= {"POWER_DAILY", "IMERG_FINAL_V07"}


def test_strategy_catalog_exposes_latest_version_cycles_and_crop_names(
    client: TestClient, login: Any, world: World
) -> None:
    """La UI muestra los ciclos de cada estrategia: latest_version + cultivo de cada componente."""
    f = world.f
    maize = f._one(
        "INSERT INTO ref.crop (code, name_es, name_en, family) VALUES ('maiz','Maíz','Maize','Poaceae') "
        "RETURNING crop_id"
    )
    bean = f._one(
        "INSERT INTO ref.crop (code, name_es, name_en, family) VALUES ('frijol','Frijol','Bean','Fabaceae') "
        "RETURNING crop_id"
    )
    v_maize = f._one(
        "INSERT INTO ref.crop_variety (crop_id, name, phenology_basis) VALUES (:c,'v','days') "
        "RETURNING variety_id",
        c=maize,
    )
    v_bean = f._one(
        "INSERT INTO ref.crop_variety (crop_id, name, phenology_basis) VALUES (:c,'v','days') "
        "RETURNING variety_id",
        c=bean,
    )
    sid = f._one(
        "INSERT INTO ref.strategy (code, name, is_reference) VALUES ('MILPA','Milpa',true) "
        "RETURNING strategy_id"
    )
    rel = f._one(
        "INSERT INTO ref.catalog_release (catalog_hash, git_sha) VALUES (repeat('8',64),'t') "
        "RETURNING catalog_release_id"
    )
    for version in (1, 2):
        svid = f._one(
            "INSERT INTO ref.strategy_version (strategy_id, version, catalog_release_id, horizon_years) "
            "VALUES (:s,:v,:r,1) RETURNING strategy_version_id",
            s=sid,
            v=version,
            r=rel,
        )
        f._exec(
            "INSERT INTO ref.strategy_cycle (strategy_version_id, cycle_idx, agri_year_offset, season, "
            "window_mode, plant_window_start, plant_window_end) VALUES (:v,1,0,'primera',"
            "'fixed_season_window','05-15','06-15')",
            v=svid,
        )
        for vid, role in ((v_maize, "principal"), (v_bean, "acompanante")):
            f._exec(
                "INSERT INTO ref.strategy_cycle_component (strategy_version_id, cycle_idx, variety_id, "
                "role, area_fraction) VALUES (:v,1,:x,:r,0.5)",
                v=svid,
                x=vid,
                r=role,
            )
    h = login(world.farmer_a_user)
    item = client.get("/v1/catalog/strategies", headers=h).json()["items"][0]
    assert item["latest_version"] == 2
    cycle = client.get(
        f"/v1/catalog/strategies/{sid}/versions/{item['latest_version']}", headers=h
    ).json()["cycles"][0]
    assert cycle["cycle_idx"] == 1 and cycle["season"] == "primera"
    assert {(c["crop_code"], c["crop_name_es"], c["role"]) for c in cycle["components"]} == {
        ("maiz", "Maíz", "principal"),
        ("frijol", "Frijol", "acompanante"),
    }
