"""Controles de privacidad reutilizables: patrones de datos sensibles y seguridad CSV.

Regla (README §22): nunca coordenadas exactas, correos, tokens ni nombres en registros, PDFs
``public`` ni datos de demostración. Estas funciones sirven al filtro de informes públicos y a
las pruebas T-S que escanean artefactos.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Coordenadas de más de tres decimales (README §22).
COORD_RE = re.compile(r"(?<![\w.])-?\d{1,3}\.\d{4,}(?![\w])")
# Un DOI (p. ej. 10.25966/564j-4331) tiene la forma de un decimal largo, pero es una cita, no una coordenada.
DOI_RE = re.compile(r"(?<![\w.])10\.\d{4,9}/\S+")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> str:
    """Neutraliza inyección de fórmulas al exportar (README §22): prefija ``'``."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def find_sensitive(text: str, *, include_uuid: bool = False) -> list[str]:
    """Devuelve categorías de datos sensibles halladas en ``text`` (vacío = limpio)."""
    found: list[str] = []
    if EMAIL_RE.search(text):
        found.append("email")
    if COORD_RE.search(DOI_RE.sub(" ", text)):
        found.append("coordinates")
    if JWT_RE.search(text):
        found.append("jwt")
    if include_uuid and UUID_RE.search(text):
        found.append("uuid")
    return found


def iter_strings(obj: Any) -> Iterable[str]:
    """Recorre recursivamente cadenas (claves y valores) de una estructura JSON."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from iter_strings(v)
    elif isinstance(obj, list | tuple | set):
        for v in obj:
            yield from iter_strings(v)
    elif obj is not None and not isinstance(obj, int | float | bool):
        yield str(obj)
