"""DTO de resultado de R2 (README §15) publicados en el OpenAPI como contrato **pendiente de R2**.

Los endpoints de análisis devuelven objetos que construye ``milpa_core`` (R2, aún inexistente); en
tiempo de ejecución R3 los transporta sin interpretarlos (``OpaqueJson``) y hoy responde 503. Para que
los clientes tipados (R4) compilen contra la forma que el README define, el OpenAPI documenta esas
respuestas con los esquemas que R4 derivó del §15 (``r2_dto_draft.json``). **No son un contrato firmado
por R2**: cada esquema lleva ``x-contract-status: pending_r2`` y se sustituirá por el real de R2.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

# Esquema opaco de R3 -> DTO del README §15 que lo documenta
PAYLOAD_TO_DTO: dict[str, str] = {
    "ClimateHistoryPayload": "ClimateHistoryDTO",
    "DekadChartPayload": "DekadChartDTO",
    "HeatmapPayload": "HeatmapDTO",
    "StrategyRiskPayload": "PageStrategyRiskDTO",
    "RankResponsePayload": "RankResponse",
    "SoilVoiPayload": "SoilVoiResponse",
}


@cache
def load_draft() -> dict[str, Any]:
    text = resources.files("api.contracts").joinpath("r2_dto_draft.json").read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def _retarget(node: Any, mapping: dict[str, str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.rsplit("/", 1)[-1] in mapping:
            node["$ref"] = "#/components/schemas/" + mapping[ref.rsplit("/", 1)[-1]]
        for v in node.values():
            _retarget(v, mapping)
    elif isinstance(node, list):
        for v in node:
            _retarget(v, mapping)


def apply_r2_dto_draft(schema: dict[str, Any]) -> None:
    """Añade los DTO pendientes de R2 y apunta a ellos las respuestas que eran opacas."""
    draft = load_draft()
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, body in draft["schemas"].items():
        if name not in components:
            components[name] = {
                **body,
                "x-contract-status": "pending_r2",
                "x-contract-owner": "R2",
                "x-source": draft["source"],
            }
    mapping = {k: v for k, v in PAYLOAD_TO_DTO.items() if k in components and v in components}
    _retarget(schema.get("paths", {}), mapping)
    for opaque in mapping:
        components.pop(opaque, None)
