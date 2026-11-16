"""Parcelas, propiedad, minimización geográfica, consentimiento, suelo/CSV y perfil (BE-03/05)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.adapters.not_integrated import default_ports
from api.adapters.ports import Ports
from testkit import INSIDE
from testkit.app import World
from testkit.doubles import FakeEvidence

LAT, LON = INSIDE


def auth(login: Any, user: dict[str, Any]) -> dict[str, str]:
    return login(user)  # type: ignore[no-any-return]


def body(world: World, **over: Any) -> dict[str, Any]:
    b: dict[str, Any] = {
        "zone_id": str(world.zone),
        "location": {"lat": LAT, "lon": LON},
        "area_ha": "1.50",
        "code": "MI-PARCELA",
    }
    b.update(over)
    return b


# ----------------------------------------------------------------------- creación y minimización
def test_farmer_creates_parcel_with_generalized_location(
    client: TestClient,
    login: Any,
    world: World,
    admin_engine: Engine,
    capfd: pytest.CaptureFixture[str],
) -> None:
    r = client.post("/v1/parcels", json=body(world), headers=auth(login, world.farmer_a_user))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["display_grid_m"] == 1000
    loc = data["display_location"]
    # redondeado a 3 decimales (centro de celda de rejilla, nunca el punto original)
    assert round(loc["lat"], 3) == loc["lat"] and round(loc["lon"], 3) == loc["lon"]
    assert str(LAT) not in r.text and str(LON) not in r.text
    # el punto exacto no está en NINGUNA fila de la base ni en los registros
    with admin_engine.connect() as c:
        dump = c.execute(
            text("SELECT p::text FROM farm.parcel p WHERE parcel_id=:i"), {"i": data["parcel_id"]}
        ).scalar_one()
    assert "14.51234" not in dump and "89.51234" not in dump
    out = capfd.readouterr().out
    assert "request" in out  # los registros SÍ se emitieron (la comprobación no es vacía)
    assert "14.51234" not in out and "89.51234" not in out


def test_generalized_point_is_snapped_to_utm_grid_of_at_least_1km(
    client: TestClient, login: Any, world: World, admin_engine: Engine
) -> None:
    r = client.post("/v1/parcels", json=body(world), headers=auth(login, world.farmer_a_user))
    pid = r.json()["parcel_id"]
    with admin_engine.connect() as c:
        x, y = c.execute(
            text(
                "SELECT ST_X(g), ST_Y(g) FROM (SELECT ST_Transform(display_geom, 32616) AS g FROM farm.parcel WHERE parcel_id=:p) t"
            ),
            {"p": pid},
        ).one()
        # el centro de una celda de 1000 m cae en (k+0.5)*1000 en ambos ejes
        assert abs((x % 1000) - 500) < 1.0 and abs((y % 1000) - 500) < 1.0
        assert (
            c.execute(
                text("SELECT display_grid_m FROM farm.parcel WHERE parcel_id=:p"), {"p": pid}
            ).scalar_one()
            >= 1000
        )


def test_point_outside_zone_is_rejected_without_echoing_coordinates(
    client: TestClient, login: Any, world: World
) -> None:
    r = client.post(
        "/v1/parcels",
        json=body(world, location={"lat": 10.123456, "lon": -80.654321}),
        headers=auth(login, world.farmer_a_user),
    )
    assert r.status_code == 422
    assert "10.123456" not in r.text and "80.654321" not in r.text


def test_unknown_zone_and_extra_fields(client: TestClient, login: Any, world: World) -> None:
    h = auth(login, world.farmer_a_user)
    assert (
        client.post("/v1/parcels", json=body(world, zone_id=str(uuid4())), headers=h).status_code
        == 404
    )
    r = client.post(
        "/v1/parcels", json={**body(world), "exact_geom": "POLYGON((0 0,1 0,1 1,0 0))"}, headers=h
    )
    assert (
        r.status_code == 422
    )  # la geometría exacta no existe en el contrato (ENABLE_EXACT_GEOMETRY=false)


def test_invalid_coordinates_and_codes_rejected(
    client: TestClient, login: Any, world: World
) -> None:
    h = auth(login, world.farmer_a_user)
    assert (
        client.post(
            "/v1/parcels", json=body(world, location={"lat": 91, "lon": 0}), headers=h
        ).status_code
        == 422
    )
    assert (
        client.post("/v1/parcels", json=body(world, code="<script>x"), headers=h).status_code == 422
    )
    assert client.post("/v1/parcels", json=body(world, area_ha="-1"), headers=h).status_code == 422


# ----------------------------------------------------------------------- roles y pertenencia
def test_technician_assignment_rules_on_create(
    client: TestClient, login: Any, world: World
) -> None:
    ok = client.post(
        "/v1/parcels",
        json=body(world, farmer_id=str(world.farmer_a)),
        headers=auth(login, world.tech),
    )
    assert ok.status_code == 201 and ok.json()["farmer_id"] == str(world.farmer_a)
    no_assign = client.post(
        "/v1/parcels",
        json=body(world, farmer_id=str(world.farmer_b)),
        headers=auth(login, world.tech),
    )
    assert no_assign.status_code == 404  # anti-enumeración
    unassigned = client.post(
        "/v1/parcels",
        json=body(world, farmer_id=str(world.farmer_a)),
        headers=auth(login, world.tech_unassigned),
    )
    assert unassigned.status_code == 404
    missing = client.post("/v1/parcels", json=body(world), headers=auth(login, world.tech))
    assert missing.status_code == 422
    admin = client.post(
        "/v1/parcels",
        json=body(world, farmer_id=str(world.farmer_a)),
        headers=auth(login, world.admin),
    )
    assert admin.status_code == 403


def test_farmer_cannot_create_for_another_farmer(
    client: TestClient, login: Any, world: World
) -> None:
    r = client.post(
        "/v1/parcels",
        json=body(world, farmer_id=str(world.farmer_b)),
        headers=auth(login, world.farmer_a_user),
    )
    assert r.status_code == 404


def test_get_parcel_ownership_matrix(client: TestClient, login: Any, world: World) -> None:
    pid = world.parcel_a
    expect = [
        (world.farmer_a_user, 200),
        (world.tech, 200),
        (world.farmer_b_user, 404),
        (world.tech_unassigned, 404),
        (world.admin, 404),
    ]
    for user, status in expect:
        r = client.get(f"/v1/parcels/{pid}", headers=auth(login, user))
        assert r.status_code == status, (user["role"], r.text)
    assert client.get(f"/v1/parcels/{pid}").status_code == 401
    assert (
        client.get(f"/v1/parcels/{uuid4()}", headers=auth(login, world.farmer_a_user)).status_code
        == 404
    )


def test_existing_and_nonexisting_foreign_parcels_are_indistinguishable(
    client: TestClient, login: Any, world: World
) -> None:
    h = auth(login, world.farmer_b_user)
    a = client.get(f"/v1/parcels/{world.parcel_a}", headers=h)
    b = client.get(f"/v1/parcels/{uuid4()}", headers=h)
    assert (a.status_code, a.json()["code"], a.json()["detail"]) == (
        b.status_code,
        b.json()["code"],
        b.json()["detail"],
    )


def test_withdrawn_consent_blocks_new_uses_but_not_reading(
    client: TestClient, login: Any, world: World
) -> None:
    world.f.withdraw(world.consent_a)
    h = auth(login, world.farmer_a_user)
    r = client.post("/v1/parcels", json=body(world), headers=h)
    assert r.status_code == 403 and r.json()["code"] == "CONSENT_REQUIRED"
    prof = client.put(
        f"/v1/parcels/{world.parcel_a}/priority-profile",
        headers=h,
        json={"w_water": "0.25", "w_soil": "0.25", "w_food": "0.25", "w_income": "0.25"},
    )
    assert prof.status_code == 403 and prof.json()["code"] == "CONSENT_REQUIRED"
    assert client.get(f"/v1/parcels/{world.parcel_a}", headers=h).status_code == 200
    # y el técnico asignado deja de ver la parcela
    assert (
        client.get(f"/v1/parcels/{world.parcel_a}", headers=auth(login, world.tech)).status_code
        == 404
    )


# ----------------------------------------------------------------------- perfil de prioridades
def test_priority_profile_upsert_and_validation(
    client: TestClient, login: Any, world: World, admin_engine: Engine
) -> None:
    h = auth(login, world.farmer_a_user)
    url = f"/v1/parcels/{world.parcel_a}/priority-profile"
    good = {
        "w_water": "0.400",
        "w_soil": "0.300",
        "w_food": "0.200",
        "w_income": "0.100",
        "constraints": {"riego": False},
    }
    assert client.put(url, json=good, headers=h).status_code == 200
    again = client.put(url, json={**good, "w_water": "0.300", "w_soil": "0.400"}, headers=h)
    assert again.status_code == 200 and again.json()["w_soil"] == "0.400"
    with admin_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM farm.priority_profile")).scalar_one() == 1
    bad_sum = client.put(url, json={**good, "w_income": "0.500"}, headers=h)
    assert bad_sum.status_code == 422
    deep = client.put(url, json={**good, "constraints": {"a": {"b": {"c": {"d": 1}}}}}, headers=h)
    assert deep.status_code == 422
    assert client.put(url, json=good, headers=auth(login, world.farmer_b_user)).status_code == 404
    assert (
        client.put(url, json={**good, "w_water": "-0.1", "w_income": "0.6"}, headers=h).status_code
        == 422
    )


# ----------------------------------------------------------------------- suelo y CSV
CSV_OK = (
    "parcel_code,sample_date,depth_from_cm,depth_to_cm,ph,ph_method\n"
    "PARCELA-A,2025-01-15,0,20,6.4,water_1_2_5\n"
    "PARCELA-A,2025-01-16,0,20,5.9,water_1_2_5\n"
)


@pytest.fixture
def evidence_ports(ports: Ports) -> Ports:
    ports.evidence = FakeEvidence()  # DOBLE DE PRUEBA de R2
    return ports


def csv_post(
    client: TestClient, world: World, headers: dict[str, str], content: bytes | str, **kw: Any
) -> Any:
    h = {**headers, "Content-Type": kw.pop("ctype", "text/csv")}
    return client.post(
        f"/v1/parcels/{world.parcel_a}/soil-samples", content=content, headers=h, **kw
    )


def test_csv_dry_run_counts_by_property(client: TestClient, login: Any, world: World) -> None:
    world.f.soil_property("ph")
    r = csv_post(
        client, world, auth(login, world.farmer_a_user), CSV_OK, params={"dry_run": "true"}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "contract": "SOIL_CSV_V1",
        "rows_total": 2,
        "rows_accepted": 2,
        "accepted_by_property": {"ph": 2},
        "persisted": False,
        "dry_run": True,
    }


def test_csv_persist_requires_evidence_port_and_never_invents_evidence(
    client: TestClient, login: Any, world: World, admin_engine: Engine
) -> None:
    world.f.soil_property("ph")
    r = csv_post(client, world, auth(login, world.farmer_a_user), CSV_OK)
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_NOT_INTEGRATED"
    with admin_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM soil.measurement")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM prov.indicator_provenance")).scalar_one() == 0


def test_csv_persist_roundtrip(
    app_engine: Engine, settings: Any, evidence_ports: Ports, dispatcher: Any, world: World
) -> None:
    from api.main import create_app

    app = create_app(
        settings,
        engine=app_engine,
        ports=evidence_ports,
        dispatcher=dispatcher,
        recover_on_start=False,
    )
    world.f.soil_property("ph", max_age=5)
    with TestClient(app) as c:
        tok = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_a_user["email"],
                "password": world.farmer_a_user["password"],
            },
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        r = c.post(
            f"/v1/parcels/{world.parcel_a}/soil-samples",
            content=CSV_OK,
            headers={**h, "Content-Type": "text/csv"},
        )
        assert r.status_code == 200 and r.json()["persisted"] is True
        soil = c.get(f"/v1/parcels/{world.parcel_a}/soil", headers=h).json()
        ph = next(p for p in soil if p["property_code"] == "ph")
        # La vista toma la medición más reciente (2025-01-16); representatividad 'parcela' (parcel_code coincide)
        assert (
            ph["status"] == "medido"
            and ph["value"]["unit"] == "pH"
            and ph["method"] == "water_1_2_5"
        )
        prov = c.get(f"/v1/provenance/{ph['value']['ip_id']}", headers=h)
        assert prov.status_code == 200 and prov.json()["provenance"] == "medido"
        assert prov.json()["evidence_rule"] == "TEST-DOUBLE-RULE"
        # otro agricultor: ni el suelo ni la procedencia son visibles
        tok_b = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_b_user["email"],
                "password": world.farmer_b_user["password"],
            },
        ).json()["access_token"]
        hb = {"Authorization": f"Bearer {tok_b}"}
        assert c.get(f"/v1/parcels/{world.parcel_a}/soil", headers=hb).status_code == 404
        assert c.get(f"/v1/provenance/{ph['value']['ip_id']}", headers=hb).status_code == 404
        # técnico asignado sí
        tok_t = c.post(
            "/v1/auth/login",
            json={"email": world.tech["email"], "password": world.tech["password"]},
        ).json()["access_token"]
        assert (
            c.get(
                f"/v1/provenance/{ph['value']['ip_id']}",
                headers={"Authorization": f"Bearer {tok_t}"},
            ).status_code
            == 200
        )


def test_csv_errors_are_per_row_and_never_echo_values(
    client: TestClient, login: Any, world: World
) -> None:
    world.f.soil_property("ph")
    bad = (
        "parcel_code,sample_date,depth_from_cm,depth_to_cm,ph,ph_method\n"
        "PARCELA-A,2025-01-15,0,20,99,water_1_2_5\n"  # fuera de rango
        "PARCELA-A,2999-01-01,0,20,6.4,water_1_2_5\n"  # fecha futura
        "PARCELA-A,2025-02-30,0,20,6.4,water_1_2_5\n"  # fecha inexistente
        "PARCELA-A,2025-01-15,30,20,6.4,water_1_2_5\n"  # profundidades invertidas
        "PARCELA-A,2025-01-15,0,20,abc,water_1_2_5\n"  # no numérico
        "PARCELA-A,2025-01-15,0,20,6.4,metodo_raro\n"  # método no aceptado
        "OTRA-PARCELA-X,2025-01-15,0,20,6.4,water_1_2_5\n"  # código de otra parcela
        "PARCELA-A,2025-01-15,0,20,,\n"
    )  # sin mediciones
    r = csv_post(client, world, auth(login, world.farmer_a_user), bad, params={"dry_run": "true"})
    assert r.status_code == 422 and r.json()["code"] == "CSV_VALIDATION_FAILED"
    errs = r.json()["errors"]
    rows = {e["loc"][1] for e in errs}
    assert rows == {1, 2, 3, 4, 5, 6, 7, 8}
    codes = {e["code"] for e in errs}
    assert {
        "out_of_range",
        "future_date",
        "invalid_date",
        "depth_order",
        "not_numeric",
        "method_not_accepted",
        "parcel_mismatch",
        "no_measurements",
    } <= codes
    for leaked in ("99", "2999-01-01", "metodo_raro", "OTRA-PARCELA-X", "abc"):
        assert leaked not in r.text


def test_csv_structure_encoding_size_and_content_type(
    client: TestClient, login: Any, world: World
) -> None:
    world.f.soil_property("ph")
    h = auth(login, world.farmer_a_user)
    p = {"dry_run": "true"}
    assert csv_post(client, world, h, "", params=p).status_code == 422  # vacío
    assert csv_post(client, world, h, "a,b\n1,2\n", params=p).status_code == 422  # columnas
    assert (
        csv_post(client, world, h, CSV_OK.encode("utf-16"), params=p).status_code == 422
    )  # codificación
    assert (
        csv_post(client, world, h, CSV_OK.replace("ph_method", "ph_metodo"), params=p).status_code
        == 422
    )
    assert csv_post(client, world, h, CSV_OK, ctype="application/json", params=p).status_code == 415
    assert csv_post(client, world, h, b"\x00" + CSV_OK.encode(), params=p).status_code == 422
    big = "x" * (3 * 1024 * 1024)  # límite de pruebas: 2 MiB por defecto
    r = csv_post(client, world, h, big, params=p)
    assert r.status_code == 413 and r.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_csv_authorization(client: TestClient, login: Any, world: World) -> None:
    world.f.soil_property("ph")
    p = {"dry_run": "true"}
    assert (
        csv_post(client, world, auth(login, world.farmer_b_user), CSV_OK, params=p).status_code
        == 404
    )
    assert (
        csv_post(client, world, auth(login, world.tech_unassigned), CSV_OK, params=p).status_code
        == 404
    )
    assert csv_post(client, world, auth(login, world.tech), CSV_OK, params=p).status_code == 200
    assert (
        client.post(
            f"/v1/parcels/{world.parcel_a}/soil-samples",
            content=CSV_OK,
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 401
    )


def test_soil_declaration_flow(
    app_engine: Engine, settings: Any, evidence_ports: Ports, dispatcher: Any, world: World
) -> None:
    from api.main import create_app

    world.f.soil_property("ph")
    url = f"/v1/parcels/{world.parcel_a}/soil-declarations/ph"
    payload = {"value": 6.2, "basis": "análisis anterior del agricultor"}
    # sin puerto de evidencia => 503 y nada guardado
    ports_no = default_ports()  # puertos NO integrados (instancia independiente)
    with TestClient(
        create_app(
            settings,
            engine=app_engine,
            ports=ports_no,
            dispatcher=dispatcher,
            recover_on_start=False,
        )
    ) as c0:
        t0 = c0.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_a_user["email"],
                "password": world.farmer_a_user["password"],
            },
        ).json()["access_token"]
        assert (
            c0.put(url, json=payload, headers={"Authorization": f"Bearer {t0}"}).status_code == 503
        )
    with TestClient(
        create_app(
            settings,
            engine=app_engine,
            ports=evidence_ports,
            dispatcher=dispatcher,
            recover_on_start=False,
        )
    ) as c:
        t = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_a_user["email"],
                "password": world.farmer_a_user["password"],
            },
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {t}"}
        ok = c.put(url, json=payload, headers=h)
        assert ok.status_code == 200 and ok.json()["unit"] == "pH"
        assert c.put(url, json={**payload, "value": 6.6}, headers=h).json()[
            "value"
        ] == pytest.approx(6.6)  # upsert
        assert c.put(url, json={**payload, "unit": "mg/kg"}, headers=h).status_code == 422
        assert c.put(url, json={**payload, "value": 99}, headers=h).status_code == 422
        assert (
            c.put(
                f"/v1/parcels/{world.parcel_a}/soil-declarations/nope", json=payload, headers=h
            ).status_code
            == 404
        )
        soil = c.get(f"/v1/parcels/{world.parcel_a}/soil", headers=h).json()
        assert next(p for p in soil if p["property_code"] == "ph")["status"] == "declarado"
        tb = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_b_user["email"],
                "password": world.farmer_b_user["password"],
            },
        ).json()["access_token"]
        assert (
            c.put(url, json=payload, headers={"Authorization": f"Bearer {tb}"}).status_code == 404
        )


def test_unmeasured_properties_are_unknown_never_zero(
    client: TestClient, login: Any, world: World
) -> None:
    world.f.soil_property("ph")
    world.f.soil_property("organic_matter", unit="%", vmin=0, vmax=100, methods=("walkley_black",))
    world.f.sample_with_measurement(world.parcel_a, "ph", 6.0)
    soil = {
        p["property_code"]: p
        for p in client.get(
            f"/v1/parcels/{world.parcel_a}/soil", headers=auth(login, world.farmer_a_user)
        ).json()
    }
    assert soil["ph"]["status"] == "medido"
    assert (
        soil["organic_matter"]["status"] == "desconocido"
        and soil["organic_matter"]["value"] is None
    )


# ----------------------------------------------------------------------- borrado (trabajo)
def test_delete_requires_owner_and_returns_202(
    client: TestClient, login: Any, world: World, dispatcher: Any
) -> None:
    for user in (world.tech, world.farmer_b_user, world.admin, world.tech_unassigned):
        assert (
            client.delete(f"/v1/parcels/{world.parcel_a}", headers=auth(login, user)).status_code
            == 404
        )
    r = client.delete(f"/v1/parcels/{world.parcel_a}", headers=auth(login, world.farmer_a_user))
    assert r.status_code == 202 and r.headers["Location"] == f"/v1/jobs/{r.json()['job_id']}"
    assert r.json()["kind"] == "parcel_delete" and r.json()["status"] == "queued"
    assert UUID(r.json()["job_id"]) in dispatcher.submitted
