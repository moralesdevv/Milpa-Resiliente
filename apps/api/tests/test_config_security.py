"""Unitarias: configuración, contraseñas, JWT, límite de tasa, paginación, redacción de logs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from api.config import Settings
from api.errors import RateLimited, Unauthenticated
from api.logging_config import JsonFormatter, redact, redact_text, request_id_var
from api.models.enums import UserRole
from api.pagination import InvalidCursor, clamp_limit, decode_cursor, encode_cursor
from api.security.passwords import MIN_PASSWORD_LEN, hash_password, needs_rehash, verify_password
from api.security.privacy import find_sensitive, sanitize_csv_cell
from api.security.ratelimit import SlidingWindowLimiter
from api.security.tokens import ALGORITHM, create_access_token, decode_access_token

SECRET = "unit-test-jwt-secret-with-at-least-32-chars!"
DB = "postgresql+psycopg://u:p@localhost/db"


def mk(**kw: object) -> Settings:
    return Settings(database_url=DB, jwt_secret=SECRET, **kw)  # type: ignore[arg-type]


# ----------------------------------------------------------------------- configuración
def test_settings_require_secret_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "JWT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_reject_unsafe_values() -> None:
    with pytest.raises(ValidationError, match="32"):
        Settings(database_url=DB, jwt_secret="corto")
    with pytest.raises(ValidationError, match="ejemplo"):
        Settings(
            database_url=DB,
            jwt_secret="change-me-change-me-change-me-change-me",
            milpa_mode="production",
        )
    with pytest.raises(ValidationError, match="CORS"):
        mk(cors_origins=["*"])
    with pytest.raises(ValidationError, match="nivel B"):
        mk(enable_exact_geometry=True)  # geometría exacta: no implementada en el MVP
    with pytest.raises(ValidationError):
        mk(display_grid_m=500)  # nunca menor a 1 km
    with pytest.raises(ValidationError, match="psycopg"):
        Settings(database_url="mysql://x/y", jwt_secret=SECRET)


def test_settings_defaults_are_safe_and_secrets_are_masked() -> None:
    s = mk()
    assert (
        s.enable_exact_geometry is False and s.milpa_mode == "sandbox" and s.demo_readonly is False
    )
    assert s.display_grid_m >= 1000 and s.cors_origins == []
    assert SECRET not in repr(s) and SECRET not in str(s.model_dump())
    assert Settings(database_url="postgresql://u:p@h/d", jwt_secret=SECRET).database_url.startswith(
        "postgresql+psycopg://"
    )


def test_cors_origins_accept_comma_separated() -> None:
    assert mk(cors_origins="https://a.example, https://b.example").cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


# ----------------------------------------------------------------------- contraseñas
def test_argon2id_hash_verify_and_policy() -> None:
    h = hash_password("una-contraseña-larga-segura")
    assert h.startswith("$argon2id$") and "una-contraseña" not in h
    assert verify_password("una-contraseña-larga-segura", h)
    assert not verify_password("otra-contraseña-larga!!", h)
    assert not verify_password(
        "x", None
    )  # usuario inexistente: verificación ficticia, siempre False
    assert not verify_password("a" * 1000, h)
    assert not needs_rehash(h)
    assert hash_password("misma-contraseña-larga-1") != hash_password(
        "misma-contraseña-larga-1"
    )  # sal única
    with pytest.raises(ValueError):
        hash_password("a" * (MIN_PASSWORD_LEN - 1))


# ----------------------------------------------------------------------- JWT
def test_jwt_roundtrip_and_claims() -> None:
    s = mk(jwt_ttl_minutes=5)
    uid = uuid4()
    tok, exp = create_access_token(s, uid, UserRole.agricultor)
    claims = decode_access_token(s, tok)
    assert claims.user_id == uid and claims.role is UserRole.agricultor and claims.jti
    assert timedelta(minutes=4) < exp - datetime.now(UTC) <= timedelta(minutes=5)
    assert jwt.get_unverified_header(tok)["alg"] == ALGORITHM


@given(junk=st.text(max_size=300))
@settings(max_examples=60, deadline=None)
def test_jwt_garbage_never_authenticates(junk: str) -> None:
    with pytest.raises(Unauthenticated):
        decode_access_token(mk(), junk)


def test_jwt_expiry_and_ttl_bounds() -> None:
    s = mk()
    tok, _ = create_access_token(
        s, uuid4(), UserRole.admin, now=datetime.now(UTC) - timedelta(hours=1)
    )
    with pytest.raises(Unauthenticated):
        decode_access_token(s, tok)
    with pytest.raises(ValidationError):
        mk(jwt_ttl_minutes=100_000)  # "vida corta"


# ----------------------------------------------------------------------- límite de tasa
def test_sliding_window_limiter() -> None:
    lim = SlidingWindowLimiter(3, window_s=10)
    for t in (0.0, 1.0, 2.0):
        lim.check("k", now=t)
    with pytest.raises(RateLimited) as e:
        lim.check("k", now=3.0)
    assert int(e.value.headers["Retry-After"]) >= 1
    lim.check("otra-clave", now=3.0)  # claves independientes
    lim.check("k", now=10.5)  # la ventana se desliza
    lim.reset()
    lim.check("k", now=0.0)


@given(n=st.integers(1, 20), extra=st.integers(1, 20))
@settings(max_examples=40, deadline=None)
def test_limiter_never_admits_more_than_limit(n: int, extra: int) -> None:
    lim = SlidingWindowLimiter(n, window_s=60)
    ok = 0
    for i in range(n + extra):
        try:
            lim.check("k", now=float(i) * 0.01)
            ok += 1
        except RateLimited:
            pass
    assert ok == n


# ----------------------------------------------------------------------- paginación
@given(vals=st.lists(st.one_of(st.text(max_size=20), st.integers(-(10**6), 10**6)), max_size=4))
def test_cursor_roundtrip(vals: list[object]) -> None:
    assert decode_cursor(encode_cursor(vals)) == vals


@given(junk=st.text(max_size=60))
def test_cursor_garbage_is_rejected_or_list(junk: str) -> None:
    try:
        out = decode_cursor(junk)
    except InvalidCursor:
        return
    assert out is None or isinstance(out, list)


def test_limit_clamping() -> None:
    s = mk(page_default_limit=10, page_max_limit=50)
    assert clamp_limit(None, s) == 10 and clamp_limit(10**9, s) == 50 and clamp_limit(-5, s) == 1
    with pytest.raises(ValidationError):
        mk(page_default_limit=60, page_max_limit=50)


# ----------------------------------------------------------------------- privacidad y registros
SENSITIVE = [
    "contacto: persona.apellido@correo.example.org",
    "lat=14.512345 lon=-89.512345",
    "Authorization: Bearer abc.def.ghi-123",
    "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.firma_firma",
    "hash $argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$aGFzaGhhc2g",
    "postgresql+psycopg://milpa_app:SuperSecreto@db:5432/milpa",
]


@pytest.mark.parametrize("text", SENSITIVE)
def test_redaction_removes_sensitive_patterns(text: str) -> None:
    out = redact_text(text)
    for leaked in (
        "persona.apellido",
        "512345",
        "abc.def.ghi",
        "firma_firma",
        "aGFzaGhhc2g",
        "SuperSecreto",
    ):
        assert leaked not in out


def test_redaction_of_keys_and_nested() -> None:
    d = redact(
        {"password": "x", "meta": {"email": "a@b.co", "ok": 1, "lat": 14.5}, "items": ["a@b.co", 3]}
    )
    assert (
        d["password"] == "[redacted]"
        and d["meta"]["email"] == "[redacted]"
        and d["meta"]["lat"] == "[redacted]"
    )
    assert d["items"] == ["[email]", 3] and d["meta"]["ok"] == 1


@given(
    user=st.from_regex(r"[a-z]{3,10}", fullmatch=True),
    dom=st.from_regex(r"[a-z]{3,10}", fullmatch=True),
    lat=st.floats(-90, 90).filter(lambda x: abs(x) > 0.001).map(lambda x: f"{x:.6f}"),
)
@settings(max_examples=80, deadline=None)
def test_redaction_property_emails_and_coordinates(user: str, dom: str, lat: str) -> None:
    text = f"usuario {user}@{dom}.org en {lat}"
    out = redact_text(text)
    assert f"{user}@{dom}.org" not in out and lat not in out


def test_json_formatter_redacts_message_extras_and_exceptions() -> None:
    token = request_id_var.set("rid-12345678")
    try:
        rec = logging.LogRecord(
            "t", logging.ERROR, __file__, 1, "falló para a@b.co en 14.123456", (), None
        )
        rec.__dict__.update({"password": "p", "route": "/x", "note": "token Bearer zzz.yyy"})
        try:
            raise ValueError("a@b.co 14.123456")
        except ValueError:
            import sys

            rec.exc_info = sys.exc_info()
        line = JsonFormatter().format(rec)
    finally:
        request_id_var.reset(token)
    data = json.loads(line)
    assert (
        data["request_id"] == "rid-12345678"
        and data["password"] == "[redacted]"
        and data["route"] == "/x"
    )
    assert data["exc_type"] == "ValueError"
    for leaked in ("a@b.co", "14.123456", "zzz.yyy"):
        assert leaked not in line


def test_find_sensitive_categories() -> None:
    assert find_sensitive("Zona Norte, 25 años, 12.5 mm") == []
    assert set(find_sensitive("a@b.co 14.123456")) == {"email", "coordinates"}
    assert find_sensitive("x", include_uuid=True) == []


@given(cell=st.text(max_size=40))
def test_csv_formula_injection_is_neutralised(cell: str) -> None:
    out = sanitize_csv_cell(cell)
    assert not out.startswith(("=", "+", "-", "@", "\t", "\r"))
    assert out == cell or out == "'" + cell


def test_csv_sanitize_examples() -> None:
    assert sanitize_csv_cell('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert (
        sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"
        and sanitize_csv_cell(None) == ""
        and sanitize_csv_cell(5) == "5"
    )


def test_cors_origins_from_environment_accepts_empty_csv_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regresión (hallada en docker compose): CORS_ORIGINS vacío rompía el arranque."""
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("JWT_SECRET", SECRET)
    for raw, expected in [
        ("", []),
        ("  ", []),
        ("https://a.example, https://b.example", ["https://a.example", "https://b.example"]),
        ('["https://c.example"]', ["https://c.example"]),
    ]:
        monkeypatch.setenv("CORS_ORIGINS", raw)
        assert Settings(_env_file=None).cors_origins == expected  # type: ignore[call-arg]
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError, match="CORS"):
        Settings(_env_file=None)  # type: ignore[call-arg]
