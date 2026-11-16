"""Esquemas comunes: error (RFC 7807 ampliado, README §15), paginación y marcas de contrato."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, RootModel
from pydantic.config import JsonDict

T = TypeVar("T")

# Marcas de estado de contrato visibles en OpenAPI (spec R3 §0.2, §10.4).
CONFIRMED: JsonDict = {"x-contract-status": "confirmed_by_spec"}
PROVISIONAL_R3: JsonDict = {
    "x-contract-status": "provisional_r3",
    "x-contract-note": "Contrato no definido en la especificación; propuesto por R3, sujeto a ADR-010.",
}


def pending(owner: str, dto: str) -> JsonDict:
    return {
        "x-contract-status": f"pending_{owner.lower()}",
        "x-contract-owner": owner,
        "x-contract-dto": dto,
        "x-contract-note": f"Forma definitiva de {dto} pendiente de {owner}; no usar como contrato.",
    }


class ErrorItem(BaseModel):
    loc: list[str | int]
    msg: str
    code: str | None = None


class ProblemDetail(BaseModel):
    """Formato de error único. ``request_id`` presente en todas las respuestas de error."""

    model_config = ConfigDict(
        json_schema_extra={
            **CONFIRMED,
            "examples": [
                {
                    "type": "https://milpa.local/errors/not-found",
                    "title": "Recurso no encontrado",
                    "status": 404,
                    "code": "NOT_FOUND",
                    "detail": "Recurso no encontrado",
                    "request_id": "5b0c1f2e-8d3a-4c9e-9a41-0f6e2a7d1c11",
                    "errors": [],
                }
            ],
        }
    )

    type: str
    title: str
    status: int
    code: str
    detail: str
    request_id: str
    errors: list[ErrorItem] = Field(default_factory=list)
    hint: str | None = None


class Page(BaseModel, Generic[T]):
    """``Page[T] = {items, next_cursor}`` (README §15)."""

    items: list[T]
    next_cursor: str | None = None


class OpaqueJson(RootModel[dict[str, Any]]):
    """Carga JSON cuyo contrato definitivo pertenece a otro rol (se documenta con pending())."""
