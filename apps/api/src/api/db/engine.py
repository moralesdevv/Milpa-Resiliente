"""Fábrica de Engines SQLAlchemy.

Regla (spec R3 §4.3/§13.5): ningún Engine/Session/conexión se comparte entre procesos. Los
engines se cachean por ``(pid, url)``: un proceso hijo (ProcessPoolExecutor, fork o spawn) nunca
reutiliza el engine del padre.
"""

from __future__ import annotations

import os
import threading

from sqlalchemy import Engine, create_engine

_lock = threading.Lock()
_engines: dict[tuple[int, str], Engine] = {}


def make_engine(url: str, *, pool_size: int = 5, max_overflow: int = 5) -> Engine:
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        # reset_on_return='rollback' (valor por defecto) revierte cualquier transacción abierta
        # al devolver la conexión: SET LOCAL no puede sobrevivir al pool.
        pool_reset_on_return="rollback",
        hide_parameters=True,  # los parámetros SQL (datos privados) nunca van a mensajes de error
    )


def get_engine(url: str) -> Engine:
    key = (os.getpid(), url)
    with _lock:
        eng = _engines.get(key)
        if eng is None:
            eng = make_engine(url)
            _engines[key] = eng
        return eng


def dispose_engines() -> None:
    with _lock:
        pid = os.getpid()
        for key in [k for k in _engines if k[0] == pid]:
            _engines.pop(key).dispose()
