"""T-S: ningún dato sensible en registros, errores, respuestas no autorizadas ni artefactos.

Regla absoluta (spec R3 §16): nunca coordenadas exactas, correos, contraseñas, tokens ni datos
sensibles en logs, PDFs públicos, paquetes de demostración, respuestas no autorizadas ni errores.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.adapters.ports import Ports
from api.main import create_app
from api.security.privacy import COORD_RE, EMAIL_RE, JWT_RE, find_sensitive
from testkit import INSIDE, PASSWORD
from testkit.app import World

ROOT = Path(__file__).resolve().parents[2]
LAT, LON = INSIDE
CSV_MARKER = "VALOR-DE-SUELO-PRIVADO-777"


def exercise_app(client: TestClient, login: Any, world: World) -> dict[str, str]:
    """Recorre flujos con datos sensibles (éxitos y fallos) y devuelve el token usado."""
    h = login(world.farmer_a_user)
    client.post(
        "/v1/auth/login",
        json={"email": world.tech["email"], "password": "contraseña-incorrecta-SECRETA"},
    )
    client.post("/v1/auth/login", json={"email": "nadie@example.org", "password": PASSWORD})
    client.post(
        "/v1/parcels",
        headers=h,
        json={
            "zone_id": str(world.zone),
            "code": "COD-PRIVADO",
            "location": {"lat": LAT, "lon": LON},
        },
    )
    client.post(
        "/v1/parcels",
        headers=h,
        json={"zone_id": str(world.zone), "location": {"lat": 10.123456, "lon": -80.654321}},
    )
    client.post(
        f"/v1/parcels/{world.parcel_a}/soil-samples",
        headers={**h, "Content-Type": "text/csv"},
        content=(
            "parcel_code,sample_date,depth_from_cm,depth_to_cm,ph,ph_method\n"
            f"{CSV_MARKER},{CSV_MARKER},0,20,{CSV_MARKER},{CSV_MARKER}\n"
        ),
        params={"dry_run": "true"},
    )
    client.get(f"/v1/parcels/{world.parcel_b}", headers=h)  # acceso denegado
    client.get("/v1/parcels/no-es-uuid", headers=h)
    client.get(
        "/v1/auth/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.firma-falsa"},
    )
    return h


def test_logs_never_contain_coordinates_emails_tokens_passwords_or_csv(
    client: TestClient, login: Any, world: World, capfd: pytest.CaptureFixture[str]
) -> None:
    h = exercise_app(client, login, world)
    out = capfd.readouterr().out
    assert out.count('"msg": "request"') >= 8, (
        "debe haber registros de acceso para que la prueba no sea vacía"
    )
    assert not COORD_RE.search(out), COORD_RE.findall(out)
    assert not EMAIL_RE.search(out), EMAIL_RE.findall(out)
    assert not JWT_RE.search(out)
    token = h["Authorization"].split()[1]
    for secret in (
        PASSWORD,
        "contraseña-incorrecta-SECRETA",
        token,
        CSV_MARKER,
        "COD-PRIVADO",
        "14.5123",
        "89.5123",
        "10.1234",
        "80.6543",
        world.farmer_a_user["email"],
        "$argon2",
        "Agricultora A",
    ):
        assert secret not in out, secret
    for line in out.splitlines():  # todo registro es JSON válido con request_id
        if line.startswith("{"):
            rec = json.loads(line)
            assert "request_id" in rec and "ts" in rec and "level" in rec


def test_no_request_bodies_or_query_strings_in_access_logs(
    client: TestClient, login: Any, world: World, capfd: pytest.CaptureFixture[str]
) -> None:
    client.get(
        "/v1/zones", params={"cursor": "SECRETO-EN-QUERY"}, headers=login(world.farmer_a_user)
    )
    out = capfd.readouterr().out
    assert "SECRETO-EN-QUERY" not in out
    assert '"route": "/zones"' in out or '"route": "/v1/zones"' in out or "zones" in out


def test_unauthorized_responses_do_not_expose_private_data(
    client: TestClient, login: Any, world: World
) -> None:
    for user in (world.farmer_b_user, world.tech_unassigned, world.admin):
        r = client.get(f"/v1/parcels/{world.parcel_a}", headers=login(user))
        assert r.status_code == 404
        blob = r.text
        for secret in (
            "PARCELA-A",
            "Agricultora A",
            str(world.farmer_a),
            world.farmer_a_user["email"],
            "Comunidad",
        ):
            assert secret not in blob
        assert not find_sensitive(blob)


def test_internal_errors_do_not_leak_details(
    app_engine: Engine, settings: Any, ports: Ports, dispatcher: Any, world: World, login: Any
) -> None:
    app = create_app(
        settings, engine=app_engine, ports=ports, dispatcher=dispatcher, recover_on_start=False
    )

    @app.get("/v1/_boom")
    def boom() -> None:  # ruta de prueba que revienta con datos sensibles en el mensaje
        raise RuntimeError(
            "fallo con persona@example.org y 14.512345,-89.512345 y postgresql://u:clave@h/d"
        )

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/v1/_boom")
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR" and r.json()["request_id"]
    for leaked in (
        "persona@example.org",
        "14.512345",
        "clave",
        "RuntimeError",
        "Traceback",
        "boom",
    ):
        assert leaked not in r.text


def test_database_errors_are_generic_503_without_connection_details(
    settings: Any, ports: Ports, dispatcher: Any
) -> None:
    from sqlalchemy import create_engine

    dead = create_engine(
        "postgresql+psycopg://usuario:clavesecreta@127.0.0.1:1/bd",
        connect_args={"connect_timeout": 1},
    )
    app = create_app(
        settings, engine=dead, ports=ports, dispatcher=dispatcher, recover_on_start=False
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/v1/auth/login", json={"email": "a@example.org", "password": "x" * 12})
    assert r.status_code == 503
    assert "clavesecreta" not in r.text and "127.0.0.1" not in r.text and "usuario" not in r.text


def test_hide_parameters_keeps_bound_values_out_of_sqlalchemy_errors(
    app_engine: Engine, test_db
) -> None:  # type: ignore[no-untyped-def]
    from api.db.engine import make_engine

    eng = make_engine(test_db.app_url)
    try:
        with eng.connect() as c, pytest.raises(Exception) as e:
            c.execute(
                text("SELECT * FROM tabla_inexistente WHERE x = :v"), {"v": "DATO-PRIVADO-123"}
            )
        assert "DATO-PRIVADO-123" not in str(e.value)
    finally:
        eng.dispose()


def test_database_stores_no_exact_coordinates_for_a_created_parcel(
    client: TestClient, login: Any, world: World, admin_engine: Engine
) -> None:
    r = client.post(
        "/v1/parcels",
        headers=login(world.farmer_a_user),
        json={"zone_id": str(world.zone), "location": {"lat": LAT, "lon": LON}},
    )
    assert r.status_code == 201
    with admin_engine.connect() as c:
        rows = (
            c.execute(
                text("SELECT p::text FROM farm.parcel p WHERE parcel_id=:i"),
                {"i": r.json()["parcel_id"]},
            )
            .scalars()
            .all()
        )
        dump = "".join(rows)
        n_private = c.execute(text("SELECT count(*) FROM private.parcel_geometry")).scalar_one()
    assert "14.5123456" not in dump and "89.5123456" not in dump
    assert n_private == 0  # geometría exacta desactivada: nada en el esquema privado


def test_openapi_and_examples_contain_no_sensitive_data() -> None:
    spec = (ROOT / "docs" / "openapi" / "openapi.json").read_text(encoding="utf-8")
    # los ejemplos de coordenadas deben tener <= 3 decimales y los correos usar el dominio reservado example.*
    assert not COORD_RE.search(spec)
    for email in EMAIL_RE.findall(spec):
        assert email.endswith(("@example.org", "@example.com")), email


def test_env_example_and_docker_files_have_no_secrets() -> None:
    patterns = [
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
    ]
    for path in [
        ROOT / ".env.example",
        ROOT / "docker-compose.yml",
        *sorted((ROOT / "infra").rglob("*")),
        *sorted((ROOT / "apps" / "api" / "src").rglob("*.py")),
    ]:
        if path.is_file():
            txt = path.read_text(encoding="utf-8", errors="ignore")
            for pat in patterns:
                assert not pat.search(txt), (path.name, pat.pattern)


def test_demo_package_has_no_personal_data_or_exact_coordinates() -> None:
    demo = ROOT / "data" / "demo"
    if not demo.is_dir():
        pytest.skip(
            "data/demo no existe: lo entrega R1. Cuando exista, esta prueba lo escanea (estado: waiting_for_dependency)"
        )
    for f in demo.rglob("*"):
        if f.is_file() and f.suffix in {".json", ".csv", ".yaml", ".yml", ".txt", ".md"}:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            assert not find_sensitive(txt), f
