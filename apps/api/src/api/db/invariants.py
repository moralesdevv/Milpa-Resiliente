"""Invariantes de seguridad de la base de datos que el arranque comprueba (falla cerrado).

Las migraciones de R3 las establecen, pero otros paquetes pueden ejecutar SQL sobre la misma base
(p. ej. los scripts de ``sql/`` de R1, ver ``docs/integration/R1_DATA_CONTRACT.md``). Un
``CREATE OR REPLACE VIEW`` sin ``security_invoker`` hace que la vista se ejecute con los privilegios
del propietario y **evada RLS** (comprobado con ``92_soil_fixture_provenance.sql`` de R1: un usuario
sin parcelas veía las filas de las parcelas ajenas). Por eso el servicio rechaza arrancar si:

* el rol de la aplicación es superusuario o tiene BYPASSRLS;
* alguna tabla que debe tener RLS la tiene desactivada;
* alguna vista de los esquemas de datos no usa ``security_invoker``.

Solo lee el catálogo de PostgreSQL; no devuelve datos de negocio.
"""

from __future__ import annotations

from sqlalchemy import Connection, Engine, text

DATA_SCHEMAS = (
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
# Tablas con filas privadas protegidas por políticas (migración 0012).
RLS_TABLES = (
    "farm.farmer",
    "farm.parcel",
    "farm.parcel_history",
    "farm.priority_profile",
    "farm.technician_assignment",
    "private.parcel_geometry",
    "report.report",
    "soil.declaration",
    "soil.measurement",
    "soil.sample",
)


class SecurityInvariantViolation(RuntimeError):
    """La base no cumple una invariante de seguridad: el servicio no debe arrancar."""


def security_violations(conn: Connection) -> list[str]:
    """Lista de violaciones (vacía si todo está en orden). Sin valores de negocio."""
    out: list[str] = []
    role = conn.execute(
        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).one_or_none()
    if role is None or role.rolsuper or role.rolbypassrls:
        out.append("el rol de la aplicación es superusuario o tiene BYPASSRLS")
    no_rls = conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname || '.' || c.relname = ANY(:t) AND NOT c.relrowsecurity ORDER BY 1"
        ),
        {"t": list(RLS_TABLES)},
    ).scalars()
    out += [f"RLS desactivada en {name}" for name in no_rls]
    present = set(
        conn.execute(
            text(
                "SELECT n.nspname || '.' || c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname || '.' || c.relname = ANY(:t)"
            ),
            {"t": list(RLS_TABLES)},
        ).scalars()
    )
    out += [f"falta la tabla protegida {name}" for name in RLS_TABLES if name not in present]
    bad_views = conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('v', 'm') AND n.nspname = ANY(:s) "
            "AND NOT COALESCE(c.reloptions @> ARRAY['security_invoker=true'], false) ORDER BY 1"
        ),
        {"s": list(DATA_SCHEMAS)},
    ).scalars()
    out += [f"la vista {name} no usa security_invoker (evade RLS)" for name in bad_views]
    return out


def assert_security_invariants(engine: Engine) -> None:
    with engine.connect() as conn:
        problems = security_violations(conn)
    if problems:
        raise SecurityInvariantViolation(
            "Invariantes de seguridad de la base incumplidas: " + "; ".join(problems)
        )
