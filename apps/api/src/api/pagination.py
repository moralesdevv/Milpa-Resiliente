"""Paginación por cursor opaco (README §15: ``Page[T] = {items, next_cursor}``)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

from api.config import Settings
from api.errors import ApiError, ErrorCode


class InvalidCursor(ApiError):
    status, code, title = 400, ErrorCode.INVALID_CURSOR, "Cursor inválido"


def encode_cursor(values: list[Any]) -> str:
    raw = json.dumps(values, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> list[Any] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursor("El cursor no es válido") from exc
    if not isinstance(data, list) or len(data) > 4:
        raise InvalidCursor("El cursor no es válido")
    return data


def clamp_limit(limit: int | None, settings: Settings) -> int:
    if limit is None:
        return settings.page_default_limit
    return max(1, min(limit, settings.page_max_limit))


def slice_page[T](
    items: list[T],
    key: Callable[[T], str],
    cursor: str | None,
    limit: int | None,
    settings: Settings,
) -> tuple[list[T], str | None]:
    """Paginación por cursor (clave) sobre una lista YA ordenada por ``key`` ascendente.

    Pensada para catálogos pequeños de R1; las listas grandes usan paginación en SQL.
    """
    n = clamp_limit(limit, settings)
    raw = decode_cursor(cursor)
    after = str(raw[0]) if raw else None
    start = (
        0 if after is None else next((i for i, x in enumerate(items) if key(x) > after), len(items))
    )
    page = items[start : start + n]
    more = start + n < len(items)
    return page, (encode_cursor([key(page[-1])]) if more and page else None)
