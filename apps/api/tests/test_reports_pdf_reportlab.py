"""PDF A4 en Python puro (ReportLab): estructura, bilingüe, privacidad, tablas, enlaces y determinismo.

Estas pruebas NO requieren Docker, Pango ni GTK: se ejecutan en cualquier host con las dependencias de
``apps/api``. La ruta HTML->WeasyPrint (opcional) se prueba aparte en ``test_reports.py``.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from api.reports import pdf as pdf_module
from api.reports.contract import ReportInput, ReportTable
from api.reports.pdf import render_pdf
from api.reports.renderer import PublicReportPrivacyError, ReportRenderError
from api.security.privacy import find_sensitive
from testkit.reports import H, make, text_of

TABLE = {
    "caption_es": "Riesgo por estrategia",
    "caption_en": "Risk by strategy",
    "headers": ["Estrategia", "Valor", "Unidad", "Evidencia"],
    "rows": [["E1 maíz de referencia", "12.3", "mm", "C"], ["E2 milpa", "9.1", "mm", "C"]],
}


def rich(**over: Any) -> ReportInput:
    sections = [
        {
            "title_es": "Sección con ñ y acentos",
            "title_en": "Section with accents",
            "body_es": "Año 2025 parcial → ≥ 9 años. Fuente: https://www.fao.org/4/s2022e/s2022e07.htm",
            "body_en": "Partial year 2025.",
            "items": ["primer punto", "segundo punto"],
            "table": TABLE,
        }
    ]
    return make(locale="es+en", summary_en="English summary.", sections=sections, **over)


def pages(pdf: bytes) -> list[Any]:
    return list(PdfReader(BytesIO(pdf)).pages)


def test_pdf_is_a4_with_structure_and_footer() -> None:
    pdf = render_pdf(rich())
    assert pdf.startswith(b"%PDF-") and len(pdf) > 5000
    reader_pages = pages(pdf)
    assert len(reader_pages) >= 2  # cuerpo + anexo técnico
    box = reader_pages[0].mediabox
    assert round(float(box.width)) == 595 and round(float(box.height)) == 842  # A4
    txt = text_of(pdf)
    for needle in (
        "Informe de decisión",
        "Decision report",
        "Resumen / Summary",
        "Anexo técnico / Technical annex",
        "Identificadores de reproducibilidad",
        "region_config_hash",
        H,  # el hash completo aparece sin cortarse
        "Supuestos / Assumptions",
        "Limitaciones / Limitations",
        "Referencias / References",
        "RESULTADO PROVISIONAL",
        "no constituye una recomendación",
        "not an automatic recommendation",
        "Página 1 de",
    ):
        assert needle in txt, needle


def test_spanish_characters_survive_extraction() -> None:
    txt = text_of(render_pdf(rich()))
    for needle in ("Sección con ñ y acentos", "Año 2025", "E1 maíz de referencia", "decisión"):
        assert needle in txt, needle
    assert (
        "->" in txt and ">=" in txt
    )  # símbolos que la fuente no trae se sustituyen, no se pierden
    assert "?" not in txt.split("Resumen")[1][:200]  # sin caracteres de reemplazo en el cuerpo


def test_monolingual_report_has_no_english_headings() -> None:
    txt = text_of(render_pdf(make()))
    assert "Technical annex" not in txt and "English summary" not in txt
    assert "Anexo técnico" in txt


def test_table_is_rendered_and_header_repeats_across_pages() -> None:
    rows = [[f"Estrategia {i:03d}", f"{i}.0", "mm", "C"] for i in range(150)]
    pdf = render_pdf(
        make(
            sections=[
                {"title_es": "Tabla larga", "body_es": "cuerpo", "table": {**TABLE, "rows": rows}}
            ]
        )
    )
    txt = text_of(pdf)
    assert "Estrategia 000" in txt and "Estrategia 149" in txt  # ninguna fila se pierde
    assert txt.count("Evidencia") >= 3  # la cabecera se repite en cada página de la tabla
    assert len(pages(pdf)) >= 4


def test_table_rendering_keeps_values_and_units_together() -> None:
    txt = text_of(render_pdf(rich()))
    assert "Riesgo por estrategia / Risk by strategy" in txt
    assert "12.3" in txt and "mm" in txt and "9.1" in txt


def test_table_contract_rejects_ragged_rows() -> None:
    with pytest.raises(ValidationError, match="tantas celdas"):
        ReportTable(headers=["a", "b"], rows=[["1"]])


def test_urls_are_clickable_links() -> None:
    reader_pages = pages(render_pdf(rich()))
    uris = []
    for page in reader_pages:
        for annot in page.get("/Annots") or []:
            action = annot.get_object().get("/A")
            if action and "/URI" in action:
                uris.append(str(action["/URI"]))
    assert "https://www.fao.org/4/s2022e/s2022e07.htm" in uris


def test_generation_is_deterministic_and_input_sensitive() -> None:
    a, b = render_pdf(rich()), render_pdf(rich())
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    other = render_pdf(rich(summary_es="Otro resumen distinto"))
    assert hashlib.sha256(a).hexdigest() != hashlib.sha256(other).hexdigest()


# ----------------------------------------------------------------------- privacidad
def test_public_pdf_has_no_internal_fields_or_sensitive_text() -> None:
    internal = {"farmer_display_name": "Persona Privada", "parcel_code": "COD-77"}
    public_txt = text_of(render_pdf(rich()))
    assert "Persona Privada" not in public_txt and "COD-77" not in public_txt
    assert find_sensitive(public_txt) == []
    internal_txt = text_of(render_pdf(rich(privacy_level="internal", internal=internal)))
    assert "Persona Privada" in internal_txt and "COD-77" in internal_txt  # el nivel interno sí


@pytest.mark.parametrize(
    "leak",
    [
        "escribir a persona@correo.example.org",
        "ubicación 14.512345, -89.512345",
        "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc12345",
    ],
)
def test_public_pdf_refuses_sensitive_text_anywhere(leak: str) -> None:
    with pytest.raises(PublicReportPrivacyError):
        render_pdf(make(summary_es=leak))
    with pytest.raises(PublicReportPrivacyError):
        render_pdf(make(annex=[{"title_es": "a", "body_es": leak}]))
    with pytest.raises(PublicReportPrivacyError):
        render_pdf(
            make(
                sections=[
                    {"title_es": "t", "body_es": "b", "table": {"headers": ["x"], "rows": [[leak]]}}
                ]
            )
        )
    assert render_pdf(make(privacy_level="internal", summary_es=leak)).startswith(b"%PDF")


# ----------------------------------------------------------------------- errores
def test_render_errors_are_wrapped_without_leaking_input(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "SECRETO-DEL-USUARIO-123"

    def boom(_data: Any) -> bytes:
        raise RuntimeError(f"fallo interno con {secret}")

    monkeypatch.setattr(pdf_module, "_build", boom)
    with pytest.raises(ReportRenderError) as caught:
        render_pdf(make())
    assert secret not in str(caught.value) and "RuntimeError" in str(caught.value)


def test_pdf_generation_needs_no_native_libraries(monkeypatch: pytest.MonkeyPatch) -> None:
    """El camino principal no importa WeasyPrint: aunque Pango falte, el PDF se genera."""
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: Any, **k: Any) -> Any:
        if name.startswith("weasyprint"):
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    assert render_pdf(rich()).startswith(b"%PDF-")
