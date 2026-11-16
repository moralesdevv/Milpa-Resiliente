"""Fixtures de la API para pruebas de integración/privacidad/contrato (usa ../conftest.py)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api.adapters.not_integrated import default_ports
from api.adapters.ports import Ports
from api.config import Settings
from api.jobs.dispatch import JobDispatcher, NullDispatcher, WorkerConfig
from api.main import create_app
from testkit import PASSWORD, Factory, TestDb
from testkit.app import World, make_settings


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def settings(test_db: TestDb, data_dir: Path) -> Settings:
    return make_settings(test_db, data_dir)


@pytest.fixture
def ports() -> Ports:
    return default_ports()


@pytest.fixture
def dispatcher() -> JobDispatcher:
    return NullDispatcher()


@pytest.fixture
def worker_config(settings: Settings) -> WorkerConfig:
    return WorkerConfig.from_settings(settings)


@pytest.fixture
def client(
    app_engine: Engine, settings: Settings, ports: Ports, dispatcher: JobDispatcher
) -> Iterator[TestClient]:
    app = create_app(
        settings, engine=app_engine, ports=ports, dispatcher=dispatcher, recover_on_start=False
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def login(client: TestClient) -> Callable[[dict[str, Any]], dict[str, str]]:
    def _login(user: dict[str, Any], password: str = PASSWORD) -> dict[str, str]:
        r = client.post("/v1/auth/login", json={"email": user["email"], "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
def world(factory: Factory) -> World:
    return World(factory)


@pytest.fixture(autouse=True)
def _dispose_worker_engines() -> Iterator[None]:
    """Los workers en línea cachean engines por (pid, url): se liberan tras cada prueba."""
    yield
    from api.db.engine import dispose_engines

    dispose_engines()
