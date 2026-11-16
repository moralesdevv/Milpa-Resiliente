"""Fixtures compartidas (unitarias, integración, privacidad, contrato).

Las pruebas de integración usan PostgreSQL 16 + PostGIS REAL. Se crea una base de datos efímera por
sesión de pruebas, se migra con Alembic desde cero y se conecta con el rol de aplicación real
(no propietario, sin BYPASSRLS), de modo que RLS se ejercita tal como en producción.

Variables: TEST_DATABASE_ADMIN_URL (superusuario/propietario), TEST_APP_ROLE / TEST_APP_ROLE_PASSWORD.
Si PostgreSQL no está disponible, las pruebas marcadas ``integration`` se OMITEN con motivo
explícito (el resultado "omitida" nunca debe leerse como aprobada).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from testkit import ADMIN_URL, APP_PASSWORD, APP_ROLE, ROOT, Factory, TestDb


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/integration/" in path or "/tests/privacy/" in path:
            item.add_marker(pytest.mark.integration)
        if "/tests/privacy/" in path:
            item.add_marker(pytest.mark.privacy)
        if "/tests/contract/" in path:
            item.add_marker(pytest.mark.contract)


@pytest.fixture(scope="session")
def pg_admin() -> Iterator[Engine]:
    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL/PostGIS de pruebas no disponible ({type(exc).__name__})")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_db(pg_admin: Engine) -> Iterator[TestDb]:
    name = f"milpa_test_{uuid.uuid4().hex[:10]}"
    with pg_admin.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_roles WHERE rolname=:r"), {"r": APP_ROLE}).first()
        if not exists:
            c.execute(
                text(
                    f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}' "
                    "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                )
            )
        c.execute(text(f'CREATE DATABASE "{name}"'))
    admin = make_url(ADMIN_URL).set(database=name)
    app = make_url(ADMIN_URL).set(database=name, username=APP_ROLE, password=APP_PASSWORD)
    cfg = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "apps" / "api" / "migrations"))
    cfg.set_main_option(
        "sqlalchemy.url", admin.render_as_string(hide_password=False).replace("%", "%%")
    )
    os.environ["APP_DB_ROLE"] = APP_ROLE
    command.upgrade(cfg, "head")
    yield TestDb(
        name, admin.render_as_string(hide_password=False), app.render_as_string(hide_password=False)
    )
    with pg_admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


_DATA_SCHEMAS = (
    "auth",
    "prov",
    "ref",
    "geo",
    "farm",
    "private",
    "soil",
    "econ",
    "engine",
    "report",
)


@pytest.fixture
def admin_engine(test_db: TestDb) -> Iterator[Engine]:
    """Conexión propietaria (para fábricas). Limpia los datos antes de cada prueba."""
    engine = create_engine(test_db.admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        tables = (
            c.execute(
                text(
                    "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables "
                    "WHERE schemaname = ANY(:s)"
                ),
                {"s": list(_DATA_SCHEMAS)},
            )
            .scalars()
            .all()
        )
        c.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


@pytest.fixture
def app_engine(test_db: TestDb, admin_engine: Engine) -> Iterator[Engine]:
    del admin_engine  # garantiza limpieza previa
    engine = create_engine(test_db.app_url, pool_size=3, max_overflow=2, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(admin_engine: Engine) -> Factory:
    return Factory(admin_engine)
