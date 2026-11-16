"""Autenticación, JWT, bloqueo progresivo, formato de error y cabeceras (BE-03, R3-F02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.config import Settings
from api.models.enums import UserRole
from api.security.tokens import ALGORITHM, create_access_token
from testkit import JWT_SECRET_TEST, PASSWORD
from testkit.app import World


def login(client: TestClient, email: str, password: str) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def test_login_and_me(client: TestClient, world: World) -> None:
    r = login(client, world.tech["email"], PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "tecnico" and me.json()["user_id"] == str(world.tech["user_id"])


def test_login_response_is_compatible_with_the_r4_session_client(
    client: TestClient, settings: Settings, world: World
) -> None:
    """R4 (`session.ts`) guarda `access_token`, `role` y `expires_in` (segundos) de la respuesta."""
    body = login(client, world.tech["email"], PASSWORD).json()
    assert body["role"] == "tecnico"
    assert body["expires_in"] == settings.jwt_ttl_minutes * 60
    exp = datetime.fromisoformat(body["expires_at"])
    assert abs((exp - datetime.now(UTC)).total_seconds() - body["expires_in"]) < 30
    assert "password" not in str(body) and body["token_type"] == "bearer"


def test_wrong_password_unknown_user_and_disabled_have_same_response(
    client: TestClient, world: World, admin_engine: Engine
) -> None:
    bad_pw = login(client, world.tech["email"], "otra-contraseña-incorrecta")
    unknown = login(client, "nadie@example.org", PASSWORD)
    with admin_engine.connect() as c:
        c.execute(
            text("UPDATE auth.app_user SET disabled_at = now() WHERE user_id=:u"),
            {"u": world.admin["user_id"]},
        )
    disabled = login(client, world.admin["email"], PASSWORD)
    for r in (bad_pw, unknown, disabled):
        assert r.status_code == 401
        assert r.json()["code"] == "UNAUTHENTICATED"
        assert r.json()["detail"] == "Credenciales inválidas"  # anti-enumeración


def test_progressive_lockout_blocks_even_correct_password(
    client: TestClient, world: World, admin_engine: Engine
) -> None:
    email = world.tech["email"]
    for _ in range(3):  # umbral de pruebas = 3
        assert login(client, email, "incorrecta-incorrecta").status_code == 401
    with admin_engine.connect() as c:
        locked = c.execute(
            text("SELECT locked_until FROM auth.app_user WHERE email=:e"), {"e": email}
        ).scalar_one()
    assert locked is not None and locked > datetime.now(UTC)
    assert login(client, email, PASSWORD).status_code == 401  # bloqueada: ni con la clave correcta
    with (
        admin_engine.connect() as c
    ):  # al expirar el bloqueo, el acceso se restablece y se limpia el contador
        c.execute(
            text(
                "UPDATE auth.app_user SET locked_until = now() - interval '1 second' WHERE email=:e"
            ),
            {"e": email},
        )
    assert login(client, email, PASSWORD).status_code == 200
    with admin_engine.connect() as c:
        assert (
            c.execute(
                text("SELECT failed_login_count FROM auth.app_user WHERE email=:e"), {"e": email}
            ).scalar_one()
            == 0
        )


def test_lock_duration_grows_and_is_capped() -> None:
    from api.services.auth import lock_duration

    s = Settings(
        database_url="postgresql+psycopg://x/y",
        jwt_secret=JWT_SECRET_TEST,
        login_lock_threshold=3,
        login_lock_base_seconds=60,
        login_lock_max_seconds=900,
    )
    assert lock_duration(2, s) is None
    assert lock_duration(3, s) == timedelta(seconds=60)
    assert lock_duration(4, s) == timedelta(seconds=120)
    assert lock_duration(50, s) == timedelta(seconds=900)


def test_missing_and_malformed_tokens_are_401_with_problem_format(client: TestClient) -> None:
    for headers in ({}, {"Authorization": "Bearer abc"}, {"Authorization": "Basic Zm9vOmJhcg=="}):
        r = client.get("/v1/auth/me", headers=headers)
        assert r.status_code == 401
        body = r.json()
        assert body["code"] == "UNAUTHENTICATED" and body["status"] == 401
        assert body["request_id"] and body["type"].startswith("https://milpa.local/errors/")
        assert r.headers["WWW-Authenticate"] == "Bearer"
        assert r.headers["content-type"].startswith("application/problem+json")


def test_expired_token_rejected(client: TestClient, settings: Settings, world: World) -> None:
    past = datetime.now(UTC) - timedelta(hours=2)
    token, _ = create_access_token(settings, world.tech["user_id"], UserRole.tecnico, now=past)
    assert (
        client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_token_with_wrong_signature_alg_none_or_audience_is_rejected(
    client: TestClient, settings: Settings, world: World
) -> None:
    now = datetime.now(UTC)
    base: dict[str, Any] = {
        "sub": str(world.admin["user_id"]),
        "role": "admin",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": "abc",
    }
    forged = [
        jwt.encode(base, "otra-clave-otra-clave-otra-clave-12345", algorithm=ALGORITHM),
        jwt.encode(base, "", algorithm="none"),
        jwt.encode({**base, "aud": "otra-api"}, JWT_SECRET_TEST, algorithm=ALGORITHM),
        jwt.encode(
            {k: v for k, v in base.items() if k != "jti"}, JWT_SECRET_TEST, algorithm=ALGORITHM
        ),
        jwt.encode(
            {**base, "sub": str(uuid4())}, JWT_SECRET_TEST, algorithm=ALGORITHM
        ),  # usuario inexistente
    ]
    for tok in forged:
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401, tok


def test_role_comes_from_database_not_from_token(
    client: TestClient, settings: Settings, world: World
) -> None:
    """Un token que afirma ser 'admin' para un técnico no eleva privilegios."""
    tok, _ = create_access_token(settings, world.tech["user_id"], UserRole.admin)
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.json()["role"] == "tecnico"


def test_rotated_previous_key_still_verifies_but_unknown_key_does_not(
    client: TestClient,
    world: World,
    test_db,
    data_dir,  # type: ignore[no-untyped-def]
) -> None:
    from testkit.app import make_settings

    old = "old-rotating-key-old-rotating-key-0123456"
    s_old = make_settings(test_db, data_dir, jwt_secret=old)
    tok, _ = create_access_token(s_old, world.tech["user_id"], UserRole.tecnico)
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    from api.jobs.dispatch import NullDispatcher
    from api.main import create_app

    app2 = create_app(
        make_settings(test_db, data_dir, jwt_secret_previous=old),
        engine=client.app.state.engine,
        dispatcher=NullDispatcher(),
        recover_on_start=False,
    )  # type: ignore[attr-defined]
    with TestClient(app2) as c2:
        assert c2.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_validation_errors_never_echo_input(client: TestClient) -> None:
    r = client.post(
        "/v1/auth/login", json={"email": "no-es-correo", "password": "SECRETO-NO-DEBE-VOLVER"}
    )
    assert r.status_code == 422
    assert "SECRETO-NO-DEBE-VOLVER" not in r.text and "no-es-correo" not in r.text
    r2 = client.post(
        "/v1/auth/login", content=b"{ esto no es json", headers={"content-type": "application/json"}
    )
    assert r2.status_code == 400 and r2.json()["code"] == "VALIDATION_ERROR"


def test_request_id_is_propagated_and_security_headers_set(client: TestClient) -> None:
    r = client.get("/healthz", headers={"X-Request-ID": "mi-request-id-001"})
    assert r.headers["X-Request-ID"] == "mi-request-id-001"
    assert (
        r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    )
    bad = client.get("/healthz", headers={"X-Request-ID": "x\ny"})  # inválido => se regenera
    assert bad.headers["X-Request-ID"] != "x\ny"
    assert client.get("/v1/no-existe").json()["code"] == "NOT_FOUND"


def test_healthz_is_public_and_reveals_nothing(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok", "db": "ok"}


def test_healthz_reports_degraded_when_db_down(settings: Settings, ports, dispatcher) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from api.main import create_app

    dead = create_engine(
        "postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    app = create_app(
        settings, engine=dead, ports=ports, dispatcher=dispatcher, recover_on_start=False
    )
    with TestClient(app) as c:
        r = c.get("/healthz")
    assert r.status_code == 503 and r.json() == {"status": "degraded", "db": "unavailable"}


def test_rate_limit_per_ip_returns_429_with_retry_after(
    app_engine: Engine, test_db, data_dir, ports, dispatcher
) -> None:  # type: ignore[no-untyped-def]
    from api.main import create_app
    from testkit.app import make_settings

    app = create_app(
        make_settings(test_db, data_dir, rate_limit_per_min=5),
        engine=app_engine,
        ports=ports,
        dispatcher=dispatcher,
        recover_on_start=False,
    )
    with TestClient(app) as c:
        codes = [c.get("/v1/auth/me").status_code for _ in range(8)]
    assert codes[:5] == [401] * 5 and set(codes[5:]) == {429}
    # el 429 mantiene el formato de error
    with TestClient(app) as c:
        r = c.get("/v1/auth/me")
    assert (
        r.status_code == 429 and r.json()["code"] == "RATE_LIMITED" and "Retry-After" in r.headers
    )


def test_cors_is_restrictive_by_default_and_wildcard_is_refused(client: TestClient) -> None:
    r = client.options(
        "/v1/auth/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers
    import pytest as _pytest

    with _pytest.raises(ValueError, match="CORS"):
        Settings(
            database_url="postgresql+psycopg://x/y", jwt_secret=JWT_SECRET_TEST, cors_origins=["*"]
        )


def test_demo_readonly_blocks_mutations_but_allows_login_and_reads(
    app_engine: Engine, test_db, data_dir, ports, dispatcher, world: World
) -> None:  # type: ignore[no-untyped-def]
    from api.main import create_app
    from testkit.app import make_settings

    app = create_app(
        make_settings(test_db, data_dir, demo_readonly=True),
        engine=app_engine,
        ports=ports,
        dispatcher=dispatcher,
        recover_on_start=False,
    )
    with TestClient(app) as c:
        tok = c.post(
            "/v1/auth/login", json={"email": world.tech["email"], "password": PASSWORD}
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert c.get("/v1/zones", headers=h).status_code == 200
        r = c.post(
            "/v1/zones",
            headers=h,
            json={
                "region_id": str(world.region),
                "name": "x",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            },
        )
        assert r.status_code == 403 and r.json()["code"] == "READ_ONLY_MODE"
