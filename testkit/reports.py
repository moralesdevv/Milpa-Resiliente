"""Ayudas de prueba para informes: entrada SINTÉTICA, extracción de texto y detección opcional de Pango."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import pytest

from api.reports.contract import ReportInput

H = "a" * 64
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def weasy_ok() -> bool:
    """WeasyPrint/Pango es una RUTA OPCIONAL (HTML->PDF): el PDF principal usa ReportLab y no la necesita."""
    try:
        from weasyprint import HTML  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


# Solo para las pruebas de la ruta HTML opcional. El PDF de ReportLab se prueba siempre, sin Docker.
needs_weasyprint = pytest.mark.skipif(
    not weasy_ok(), reason="WeasyPrint/Pango (ruta HTML opcional) no disponible en este host"
)
needs_pdf = needs_weasyprint  # alias histórico: prefiera needs_weasyprint


def make(**over: Any) -> ReportInput:
    # ENTRADA SINTÉTICA DE PRUEBA: ninguna cifra es científica.
    data: dict[str, Any] = {
        "locale": "es",
        "privacy_level": "public",
        "zone_name": "Zona de prueba",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "hashes": {
            "code_version": "test-sha",
            "region_config_hash": H,
            "catalog_hash": "b" * 64,
            "data_hash": "c" * 64,
            "params_hash": "d" * 64,
            "seed": 42,
        },
        "generated_at": NOW,
        "summary_es": "Resumen de prueba.",
        "sections": [
            {"title_es": "Sección 1", "body_es": "Cuerpo de prueba.", "items": ["a", "b"]}
        ],
        "annex": [{"title_es": "Anexo A", "body_es": "Detalle técnico de prueba."}],
        "references": [{"text": "Referencia de prueba", "product_version": "v1"}],
        "assumptions": ["supuesto 1"],
        "limitations": ["limitación 1"],
        "provenance_notes": ["nota"],
    }
    data.update(over)
    return ReportInput.model_validate(data)


def text_of(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
