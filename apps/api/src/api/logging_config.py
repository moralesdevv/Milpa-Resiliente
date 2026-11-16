"""Registros JSON estructurados con redacción obligatoria (spec R3 §18, README §22).

Reglas: sin cuerpos de petición, sin coordenadas con más de tres decimales, sin correos,
tokens, JWT ni hashes de contraseña. La redacción se aplica al mensaje y a todo campo extra.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REDACTED = "[redacted]"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Query strings de URL: pueden llevar cursores, identificadores o secretos.
    (re.compile(r"(\S+?)\?[^\s\"']+"), r"?[query-redacted]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[jwt]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [token]"),
    (re.compile(r"\$argon2[a-z]*\$[^\s\"']+"), "[password-hash]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    # Coordenadas: decimales con más de tres dígitos (README §22).
    (re.compile(r"(?<![\w.])-?\d{1,3}\.\d{4,}(?![\w])"), "[coord]"),
    (re.compile(r"(?i)\b(postgres(?:ql)?(?:\+\w+)?://[^:\s/]+:)[^@\s]+@"), r"\1[redacted]@"),
]

_SENSITIVE_KEYS = frozenset(
    {
        "password", "passwd", "token", "access_token", "authorization", "secret", "jwt",
        "jwt_secret", "email", "lat", "lon", "lng", "latitude", "longitude", "location",
        "geom", "geometry", "body", "csv", "content", "display_name", "community", "cookie",
        "database_url", "api_key",
    }
)  # fmt: skip

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def redact_text(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact(v) for v in value]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return redact_text(str(value))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = redact(v, k)
        if record.exc_info:
            # Solo el tipo de excepción: el mensaje o el traceback pueden contener datos privados.
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)


class StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Escribe en el ``sys.stdout`` ACTUAL en cada emisión (no el vigente al crearse el handler)."""

    def __init__(self) -> None:
        super().__init__()

    @property
    def stream(self) -> Any:
        return sys.stdout

    @stream.setter
    def stream(self, _: Any) -> None:
        return None


def configure_logging(level: str = "INFO") -> None:
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # El access log de uvicorn incluye query strings: se sustituye por nuestro middleware.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").handlers = []
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # no registrar SQL/params
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "multipart",
        "asyncio",
        "weasyprint",
        "fontTools",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)  # registran URL completas / ruido
