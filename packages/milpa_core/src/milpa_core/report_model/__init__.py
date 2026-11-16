"""Ensamblado del modelo del informe (SE-11). Sin formato: la plantilla Jinja2 de R4/R3 lo presenta."""
from __future__ import annotations

from typing import Any

from ..serialize import to_jsonable


def build_report(summary: dict, rank: dict | None, voi: dict | None, scenarios: list[dict] | None,
                 locale: str = "es") -> dict[str, Any]:
    sections = [
        {"id": "resumen", "title_es": "Resumen", "content": {
            "modo": summary["mode"], "etiqueta": summary["label"], "escenario": summary["scenario"]["scenario_id"],
            "advertencia": "Indicador de exposición climática; no es predicción de rendimiento ni de cosecha."}},
        {"id": "riesgo", "title_es": "Riesgo por estrategia", "content": summary["strategies"]},
    ]
    if rank:
        sections.append({"id": "ranking", "title_es": "Comparación de estrategias", "content": rank})
    if scenarios:
        sections.append({"id": "escenarios", "title_es": "Escenarios sintéticos (no son pronóstico)", "content": scenarios})
    if voi:
        sections.append({"id": "suelo", "title_es": "Valor de la información del suelo (pH)", "content": voi})
    annex = [
        {"id": "procedencia", "title_es": "Procedencia y evidencia", "content": summary["meta"]},
        {"id": "supuestos", "title_es": "Supuestos y limitaciones", "content": summary["limitations"]},
        {"id": "decisiones", "title_es": "Registro de decisiones del ranking", "content": (rank or {}).get("decision_log")},
        {"id": "modo", "title_es": "Por qué este modo de cálculo", "content": summary["mode_reasons"]},
    ]
    return to_jsonable({"locale": locale, "sections": sections, "annex": annex})
