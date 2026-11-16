"""Comprobación de salud (sin datos sensibles)."""

from __future__ import annotations

from sqlalchemy import Engine, text


def database_ok(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
