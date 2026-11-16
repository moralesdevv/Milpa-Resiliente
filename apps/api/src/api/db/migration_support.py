"""Utilidades de migración: ejecutar DDL desde archivos SQL versionados (``migrations/sql``)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from alembic import context, op

SQL_DIR = Path(__file__).resolve().parents[3] / "migrations" / "sql"
_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def app_role() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    role = x_args.get("app_role") or os.environ.get("APP_DB_ROLE", "milpa_app")
    if not _ROLE_RE.match(role):
        raise ValueError("Nombre de rol de aplicación inválido")
    return role


def run_up(name: str) -> None:
    sql = (SQL_DIR / f"{name}.up.sql").read_text(encoding="utf-8")
    sql = sql.replace("{app_role}", app_role())
    # exec_driver_sql evita que SQLAlchemy interprete ':' del DDL; psycopg exige duplicar '%'
    # (p. ej. la unidad '%' de ref.soil_property).
    op.get_bind().exec_driver_sql(sql.replace("%", "%%"))


def run_statements(*statements: str) -> None:
    for stmt in statements:
        op.get_bind().exec_driver_sql(stmt)
