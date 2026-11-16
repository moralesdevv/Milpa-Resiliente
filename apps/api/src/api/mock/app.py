"""Servidor MOCK del OpenAPI v0 (BE-02). ``make mock`` -> http://localhost:4010

Reglas (spec R3 §10.4):
  * Solo devuelve EJEMPLOS ESTRUCTURALES documentados en los esquemas (campo ``examples``).
  * Toda respuesta lleva ``X-Milpa-Mock: fixture`` y un cuerpo etiquetado cuando es un objeto.
  * Nunca simula cálculos: los endpoints cuyo DTO pertenece a R2 (``x-contract-status: pending_r2``)
    o que no tienen ejemplo documentado responden 501 explicando por qué.
  * No valida credenciales ni toca base de datos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

HEADERS = {"X-Milpa-Mock": "fixture", "Cache-Control": "no-store"}
DEFAULT_SPEC = Path(__file__).resolve().parents[5] / "docs" / "openapi" / "openapi.json"


def _resolve(spec: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not ref:
        return node
    cur: Any = spec
    for part in ref.removeprefix("#/").split("/"):
        cur = cur[part]
    return cur  # type: ignore[no-any-return]


def example_for(spec: dict[str, Any], schema: dict[str, Any]) -> tuple[Any, str] | tuple[None, str]:
    """(ejemplo, motivo). Compone listas/páginas SOLO a partir de ejemplos documentados."""
    node = _resolve(spec, schema)
    if node.get("x-contract-status", "").startswith("pending_"):
        return None, f"contrato definitivo pendiente de {node.get('x-contract-owner', 'otro rol')}"
    if node.get("examples"):
        return node["examples"][0], "ok"
    if node.get("type") == "array" and "items" in node:
        item, why = example_for(spec, node["items"])
        return ([item], "ok") if why == "ok" else (None, why)
    props = node.get("properties", {})
    if "items" in props and "next_cursor" in props:
        item, why = example_for(spec, props["items"])
        return ({"items": item, "next_cursor": None}, "ok") if why == "ok" else (None, why)
    return None, "sin ejemplo documentado en el esquema"


def build_mock(spec: dict[str, Any]) -> Starlette:
    routes: list[Route] = []

    def make_handler(method: str, path: str, op: dict[str, Any]) -> Any:
        ok_code = next((c for c in sorted(op["responses"]) if c.startswith("2")), "200")
        resp = op["responses"][ok_code]
        content = resp.get("content", {}).get("application/json")
        if content is None:  # p. ej. descarga de PDF: no se sirve contenido simulado
            payload, why = None, "respuesta no JSON (p. ej. PDF): el mock no fabrica binarios"
        else:
            payload, why = example_for(spec, content["schema"])

        async def handler(_: Request) -> Response:
            if payload is None:
                return JSONResponse(
                    {
                        "mock": True,
                        "status": 501,
                        "code": "MOCK_NO_EXAMPLE",
                        "detail": f"{method.upper()} {path}: {why}",
                    },
                    status_code=501,
                    headers=HEADERS,
                )
            body = payload if not isinstance(payload, dict) else {**payload, "_mock": "fixture"}
            return JSONResponse(body, status_code=int(ok_code), headers=HEADERS)

        return handler

    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            routes.append(Route(path, make_handler(method, path, op), methods=[method.upper()]))
    return Starlette(routes=routes)


def load_spec(path: Path = DEFAULT_SPEC) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def __getattr__(name: str) -> Starlette:
    # `uvicorn api.mock.app:app` construye el mock bajo demanda (importar el módulo no exige el OpenAPI).
    if name == "app":
        return build_mock(load_spec())
    raise AttributeError(name)
