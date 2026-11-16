"""Entorno Alembic. Cadena ÚNICA de migraciones del monorepo (ADR-003).

La URL se toma, en orden: ``-x url=...``, ``sqlalchemy.url`` programático (pruebas),
``MIGRATION_DATABASE_URL`` (rol propietario) y ``DATABASE_URL``. Las migraciones se ejecutan
con un rol propietario; la aplicación en tiempo de ejecución usa otro rol sin BYPASSRLS.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
target_metadata = None  # migraciones SQL explícitas (DDL revisado), sin autogenerate


def _url() -> str:
    x = context.get_x_argument(as_dictionary=True)
    url = (
        x.get("url")
        or config.get_main_option("sqlalchemy.url")
        or os.environ.get("MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("Defina MIGRATION_DATABASE_URL (o DATABASE_URL) para migrar")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
