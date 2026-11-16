"""Migraciones: desde base vacía, reversibles, orden del spec y rol de aplicación seguro."""

from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from testkit import ADMIN_URL, APP_ROLE, ROOT, TestDb

SCHEMAS = ["auth", "prov", "ref", "geo", "farm", "private", "soil", "econ", "engine", "report"]
RLS_TABLES = {
    "farm.farmer",
    "farm.parcel",
    "farm.parcel_history",
    "farm.priority_profile",
    "farm.technician_assignment",
    "private.parcel_geometry",
    "soil.sample",
    "soil.measurement",
    "soil.declaration",
    "report.report",
}


def _cfg(url: str) -> Config:
    cfg = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "apps" / "api" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def test_schemas_and_tables_exist(test_db: TestDb, admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        schemas = set(c.execute(text("SELECT nspname FROM pg_namespace")).scalars())
        assert set(SCHEMAS) <= schemas
        n = c.execute(
            text("SELECT count(*) FROM pg_tables WHERE schemaname = ANY(:s)"), {"s": SCHEMAS}
        ).scalar_one()
        assert n >= 45
        assert (
            c.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname='postgis'")
            ).scalar_one()
            == 1
        )
        assert c.execute(text("SELECT to_regclass('engine.job')")).scalar_one() is not None


def test_rls_enabled_on_all_private_tables(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        rows = c.execute(
            text("SELECT schemaname||'.'||tablename FROM pg_tables WHERE rowsecurity")
        ).scalars()
        assert set(rows) >= RLS_TABLES


def test_application_role_cannot_bypass_rls(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        role = c.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=:r"
            ),
            {"r": APP_ROLE},
        ).one()
        assert tuple(role) == (False, False, False, False)
        owned = c.execute(
            text("SELECT count(*) FROM pg_tables WHERE tableowner=:r AND schemaname = ANY(:s)"),
            {"r": APP_ROLE, "s": SCHEMAS},
        ).scalar_one()
        assert owned == 0, (
            "el rol de aplicación no debe ser propietario de tablas (evita bypass de RLS)"
        )


def test_app_role_cannot_alter_policies(app_engine: Engine) -> None:
    with (
        app_engine.connect() as c,
        pytest.raises(Exception, match=r"must be owner|permission denied"),
    ):
        c.execute(text("ALTER TABLE farm.parcel DISABLE ROW LEVEL SECURITY"))


def test_property_status_view_is_security_invoker(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        opts = c.execute(
            text("SELECT reloptions FROM pg_class WHERE oid = 'soil.property_status'::regclass")
        ).scalar_one()
        assert any("security_invoker=true" in o for o in opts)


def test_ref_strategy_region_fk_is_deferred_to_geo_revision(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        fk = c.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname='strategy_region_fk' AND contype='f'")
        ).first()
        assert fk is not None


def test_job_kind_check_includes_extensions(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        defn = c.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='engine.job'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%zone_ingest%'"
            )
        ).scalar_one()
        for kind in (
            "zone_ingest",
            "analysis_run",
            "scenario_run",
            "report",
            "parcel_delete",
            "consent_purge",
        ):
            assert kind in defn


def test_migrations_are_reversible_from_scratch(pg_admin: Engine) -> None:
    """Base vacía -> head -> base -> head (spec R3 §21.2)."""
    name = f"milpa_mig_{uuid.uuid4().hex[:8]}"
    with pg_admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        url = make_url(ADMIN_URL).set(database=name).render_as_string(hide_password=False)
        os.environ["APP_DB_ROLE"] = APP_ROLE
        cfg = _cfg(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        eng = create_engine(url)
        with eng.connect() as c:
            left = c.execute(
                text("SELECT count(*) FROM pg_tables WHERE schemaname = ANY(:s)"), {"s": SCHEMAS}
            ).scalar_one()
            assert left == 0
        eng.dispose()
        command.upgrade(cfg, "head")
        eng = create_engine(url)
        with eng.connect() as c:
            assert c.execute(text("SELECT to_regclass('farm.parcel')")).scalar_one() is not None
            # datos de referencia de R1 (migración 0014): fuentes y propiedades de suelo
            codes = set(c.execute(text("SELECT code FROM prov.data_source")).scalars())
            assert codes == {"POWER_DAILY", "IMERG_FINAL_V07", "SOIL_CSV_FIXTURE"}
            props = set(c.execute(text("SELECT code FROM ref.soil_property")).scalars())
            assert props == {
                "ph",
                "organic_matter",
                "sand",
                "silt",
                "clay",
                "cec",
                "effective_depth",
                "awc",
            }
            # IMERG no redistribuible hasta verificar su licencia (DE-12/DP-14)
            assert not c.execute(
                text("SELECT redistributable FROM prov.data_source WHERE code='IMERG_FINAL_V07'")
            ).scalar_one()
        eng.dispose()
    finally:
        with pg_admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def test_migration_fails_if_app_role_missing(pg_admin: Engine) -> None:
    name = f"milpa_mig_{uuid.uuid4().hex[:8]}"
    with pg_admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        url = make_url(ADMIN_URL).set(database=name).render_as_string(hide_password=False)
        os.environ["APP_DB_ROLE"] = "rol_que_no_existe"
        with pytest.raises(Exception, match="no existe"):
            command.upgrade(_cfg(url), "head")
    finally:
        os.environ["APP_DB_ROLE"] = APP_ROLE
        with pg_admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
