"""Utilidades compartidas por los routers (sin lógica de negocio)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import Path, Request, Response

from api.errors import PayloadTooLarge, UnsupportedMediaType
from api.schemas.common import ProblemDetail
from api.schemas.jobs import JobOut
from api.services.jobs import job_location, to_out

# Parámetros de ruta: la especificación (README §16) escribe las plantillas con `{id}`, `{v}` y
# `{property}`. Los clientes tipados (openapi-fetch) indexan las rutas por su plantilla literal, así
# que el OpenAPI debe usar esos nombres; en el código se conservan nombres descriptivos.
ZoneId = Annotated[UUID, Path(alias="id", description="Identificador de la zona")]
ParcelId = Annotated[UUID, Path(alias="id", description="Identificador de la parcela")]
RunId = Annotated[UUID, Path(alias="id", description="Identificador de la corrida")]
ReportId = Annotated[UUID, Path(alias="id", description="Identificador del informe")]
JobId = Annotated[UUID, Path(alias="id", description="Identificador del trabajo")]
StrategyId = Annotated[UUID, Path(alias="id", description="Identificador de la estrategia")]
StrategyVersionNo = Annotated[
    int, Path(alias="v", ge=1, le=2_147_483_647, description="Número de versión de la estrategia")
]
SoilPropertyCode = Annotated[str, Path(alias="property", description="Código de propiedad")]


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        400: "Solicitud mal formada",
        401: "No autenticado",
        403: "Acceso denegado",
        404: "Recurso inexistente o no visible",
        409: "Conflicto de estado",
        413: "Contenido demasiado grande",
        415: "Tipo de contenido no admitido",
        422: "Error de validación",
        429: "Límite de tasa superado",
        503: "Dependencia o dato no disponible",
    }
    return {c: {"model": ProblemDetail, "description": descriptions[c]} for c in codes}


AUTHED = error_responses(401, 403, 429)


def accepted(job: Any, response: Response) -> JobOut:
    """202 Accepted + Location (spec R3 §13.5)."""
    response.status_code = 202
    response.headers["Location"] = job_location(job.job_id)
    return to_out(job)


def not_modified(request: Request, etag: str) -> Response | None:
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return None


async def read_limited_body(
    request: Request, max_bytes: int, allowed_types: tuple[str, ...]
) -> bytes:
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype not in allowed_types:
        raise UnsupportedMediaType(f"Content-Type debe ser uno de: {', '.join(allowed_types)}")
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise PayloadTooLarge(f"El cuerpo excede {max_bytes // (1024 * 1024)} MiB")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:  # corta la lectura: no se acumula más memoria
            raise PayloadTooLarge(f"El cuerpo excede {max_bytes // (1024 * 1024)} MiB")
        chunks.append(chunk)
    return b"".join(chunks)
