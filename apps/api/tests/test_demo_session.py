"""Sesión pública de demostración: alcance limitado, desactivable y sin credenciales utilizables."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.config import Settings
from api.models.enums import UserRole
from api.security.demo import demo_allows
from api.security.tokens import create_access_token, decode_access_token
from testkit import JWT_SECRET_TEST


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret=JWT_SECRET_TEST,
        demo_public_access=True,
    )


RUN = "/v1/runs/0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10"
ZONE = "/v1/zones/0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/v1/zones"),
        ("GET", f"{RUN}/summary"),
        ("GET", f"{RUN}/heatmap"),
        ("GET", "/v1/catalog/strategies"),
        ("POST", f"{ZONE}/runs"),
        ("POST", f"{RUN}/scenarios"),
        ("POST", f"{RUN}/rank"),
        ("POST", "/v1/reports"),
    ],
)
def test_demo_scope_allows_exploration(method: str, path: str) -> None:
    assert demo_allows(method, path)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/v1/parcels/0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10"),
        ("GET", "/v1/parcels/0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10/soil"),
        ("POST", "/v1/parcels"),
        ("POST", f"{RUN}/soil-voi"),
        ("DELETE", f"{RUN}"),
        ("PUT", "/v1/parcels/0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10/soil-declarations/ph"),
        ("POST", "/v1/auth/login"),
        ("GET", "/v1/admin/anything"),
    ],
)
def test_demo_scope_blocks_private_and_administrative_operations(method: str, path: str) -> None:
    assert not demo_allows(method, path)


def test_demo_token_carries_the_demo_claim_and_a_longer_but_bounded_life() -> None:
    s = settings()
    token, expires = create_access_token(s, uuid4(), UserRole.tecnico, demo=True)
    claims = decode_access_token(s, token)
    assert claims.demo is True and claims.role == UserRole.tecnico
    assert abs((expires - claims.expires_at).total_seconds()) < 1
    normal, _ = create_access_token(s, uuid4(), UserRole.tecnico)
    assert decode_access_token(s, normal).demo is False
