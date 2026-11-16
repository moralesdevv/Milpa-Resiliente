"""Informes (BE-07): contrato de entrada, plantilla provisional, privacidad, SSRF y PDF.

Las pruebas marcadas ``pdf`` requieren Pango (WeasyPrint). En el host Windows se OMITEN con motivo
explícito y se ejecutan dentro de la imagen Docker (``make test-docker``).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from io import BytesIO
from typing import Any

import pytest
from pydantic import ValidationError

from api.reports.contract import ReportSection
from api.reports.renderer import (
    DISCLAIMER_ES,
    FetchGuard,
    PublicReportPrivacyError,
    ReportRenderError,
    html_to_pdf,
    render_html,
)
from api.security.privacy import find_sensitive
from testkit.reports import H, make, needs_pdf, text_of


# ----------------------------------------------------------------------- contrato de entrada
def test_input_contract_validation() -> None:
    with pytest.raises(ValidationError, match="summary_en"):
        make(locale="es+en")
    with pytest.raises(ValidationError, match="interno"):
        make(internal={"farmer_display_name": "X"})  # público + campos internos
    with pytest.raises(ValidationError, match="zona horaria"):
        make(generated_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        make(hashes={**make().hashes.model_dump(), "data_hash": "no-es-hash"})
    with pytest.raises(ValidationError):
        make(inventado="x")
    with pytest.raises(ValidationError):
        make(summary_es="x" * 9000)
    assert (
        make(privacy_level="internal", internal={"farmer_display_name": "X"}).internal is not None
    )
    assert ReportSection(title_es="t", body_es="b").items == []


# ----------------------------------------------------------------------- plantilla
def test_template_is_labelled_provisional_and_has_required_content() -> None:
    html = render_html(make())
    assert "PLANTILLA TÉCNICA PROVISIONAL" in html and "provisional-technical-v0" in html
    assert DISCLAIMER_ES in html  # "no constituye una recomendación automática"
    for expected in (
        "Anexo técnico",
        "run_id",
        "code_version",
        "region_config_hash",
        "catalog_hash",
        "data_hash",
        "params_hash",
        "seed",
        "Supuestos",
        "Limitaciones",
        "Referencias",
        "Procedencia y evidencia",
        H,
        "versión del producto: v1",
        "Zona de prueba",
    ):
        assert expected in html, expected
    assert "dcterms.created" in html and "2026-11-14T12:00:00+00:00" in html


def test_bilingual_summary_and_titles() -> None:
    html = render_html(
        make(
            locale="es+en",
            summary_en="English summary.",
            sections=[
                {"title_es": "Sección", "title_en": "Section", "body_es": "c", "body_en": "body"}
            ],
        )
    )
    assert (
        "English summary." in html
        and "Section" in html
        and "not an automatic recommendation" in html
    )
    assert "English summary." not in render_html(make())


def test_autoescape_and_no_template_injection() -> None:
    payload = "<script>alert(1)</script> {{ 7*7 }} {% for x in y %}"
    html = render_html(
        make(summary_es=payload, sections=[{"title_es": payload, "body_es": payload}])
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert (
        "49" not in re.sub(r"[^0-9]", " ", html.split("Resumen", 1)[1][:200]).split()
    )  # {{ 7*7 }} no se evalúa
    assert (
        "{{ 7*7 }}" in html or "&#123;&#123;" in html or "{{ 7*7 }}" in html.replace("&#123;", "{")
    )


def test_internal_fields_only_in_internal_reports() -> None:
    internal = render_html(
        make(
            privacy_level="internal",
            internal={"farmer_display_name": "Nombre Privado", "parcel_code": "COD-77"},
        )
    )
    assert "Nombre Privado" in internal and "COD-77" in internal
    public = render_html(make())
    assert (
        "Nombre Privado" not in public and "COD-77" not in public and "Agricultor/a" not in public
    )


@pytest.mark.parametrize(
    "leak",
    [
        "escribir a persona@correo.example.org",
        "ubicación 14.512345, -89.512345",
        "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc12345",
    ],
)
def test_public_report_refuses_to_render_sensitive_data(leak: str) -> None:
    with pytest.raises(PublicReportPrivacyError):
        render_html(make(summary_es=leak))
    with pytest.raises(PublicReportPrivacyError):
        render_html(make(annex=[{"title_es": "a", "body_es": leak}]))
    render_html(
        make(privacy_level="internal", summary_es=leak)
    )  # el filtro es de informes públicos


def test_public_html_is_clean_for_normal_content() -> None:
    assert find_sensitive(render_html(make())) == []


# ----------------------------------------------------------------------- SSRF / recursos externos
def test_fetch_guard_denies_everything_but_data_uris() -> None:
    g = FetchGuard()
    for url in [
        "http://169.254.169.254/latest/meta-data/",
        "https://intranet.local/x?token=SECRETO",
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "ftp://h/x",
        "gopher://h",
        "//host/x",
        "relativo.css",
    ]:
        with pytest.raises(ValueError, match="denegado"):
            g(url)
    assert len(g.denied) == 8
    assert all("SECRETO" not in d for d in g.denied)  # no se guardan query strings


def test_fetch_guard_allows_data_uris_and_counts_them() -> None:
    g = FetchGuard()
    assert g.check("data:text/plain;base64,aG9sYQ==") is None and g.allowed_data_uris == 1
    assert g.denied == []


@needs_pdf
def test_ssrf_attempts_in_html_are_blocked_and_pdf_still_renders() -> None:
    hostile = """<html><head>
      <link rel="stylesheet" href="http://169.254.169.254/latest/meta-data/iam">
      <link rel="stylesheet" href="file:///etc/passwd">
      <style>@import url("http://interno.local/x.css"); body{background:url(file:///etc/hostname)}</style>
    </head><body><img src="http://127.0.0.1:9/x.png"><img src="file:///etc/passwd"><p>contenido</p></body></html>"""
    guard = FetchGuard()
    pdf = html_to_pdf(hostile, guard)
    assert pdf.startswith(b"%PDF")
    assert guard.denied, (
        "los intentos de recuperar recursos deben pasar por el guardia y ser denegados"
    )
    joined = " ".join(guard.denied)
    assert "169.254.169.254" in joined and "file:///etc/passwd" in joined and "127.0.0.1" in joined


# ----------------------------------------------------------------------- PDF
@needs_pdf
def test_pdf_is_generated_with_expected_structure_and_sha256() -> None:
    pdf = html_to_pdf(render_html(make()))
    assert pdf.startswith(b"%PDF-") and len(pdf) > 2000
    txt = text_of(pdf)
    for needle in (
        "Informe de decisión",
        "Anexo técnico",
        "PLANTILLA TÉCNICA PROVISIONAL",
        "no constituye una recomendación",
    ):
        assert needle in txt, needle
    assert hashlib.sha256(pdf).hexdigest() == hashlib.sha256(bytes(pdf)).hexdigest()
    from pypdf import PdfReader

    assert len(PdfReader(BytesIO(pdf)).pages) >= 2  # página principal + anexo


@needs_pdf
def test_pdf_generation_is_deterministic() -> None:
    a = html_to_pdf(render_html(make()))
    b = html_to_pdf(render_html(make()))
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    c = html_to_pdf(render_html(make(summary_es="Otro resumen")))
    assert hashlib.sha256(a).hexdigest() != hashlib.sha256(c).hexdigest()


@needs_pdf
def test_public_pdf_text_has_no_personal_data_or_coordinates() -> None:
    internal_secret = "Persona Privada"
    pdf = html_to_pdf(render_html(make()))
    txt = text_of(pdf)
    assert internal_secret not in txt and find_sensitive(txt) == []
    pdf_int = html_to_pdf(
        render_html(
            make(privacy_level="internal", internal={"farmer_display_name": internal_secret})
        )
    )
    assert internal_secret in text_of(pdf_int)  # el nivel interno sí lo muestra


def test_missing_native_libs_gives_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: Any, **k: Any) -> Any:
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(ReportRenderError, match="Docker"):
        html_to_pdf("<p>x</p>")


@needs_pdf
def test_data_uri_images_still_render_inside_the_restricted_fetcher() -> None:
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    guard = FetchGuard()
    pdf = html_to_pdf(
        f'<html><body><img src="data:image/png;base64,{png}"><p>x</p></body></html>', guard
    )
    assert pdf.startswith(b"%PDF") and guard.allowed_data_uris >= 1 and guard.denied == []
