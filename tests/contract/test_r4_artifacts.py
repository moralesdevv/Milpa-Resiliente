"""Compatibilidad de R3 con los artefactos REALES entregados por R4 (``references/R4``).

R4 entregó (a) un OpenAPI **borrador local** derivado de la especificación, (b) un cliente tipado que
lo consume y (c) la plantilla Jinja2 del informe. Ninguno es contrato oficial firmado. Estas pruebas
leen los archivos tal cual; si ``references/R4`` no existe, se omiten con motivo. Las diferencias
conocidas se enumeran de forma explícita: cualquier diferencia nueva (de cualquiera de los dos lados)
hace fallar la prueba. Detalle: ``docs/auditoria/matriz_compatibilidad.md``.
"""

from __future__ import annotations

import io
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
import yaml

from api.contracts import provisional_enums as mirror
from api.reports.renderer import (
    FetchGuard,
    PublicReportPrivacyError,
    ReportRenderError,
    html_to_pdf,
    inline_local_stylesheets,
    render_template_pack,
)
from testkit import ROOT
from testkit.reports import needs_pdf

R4 = ROOT / "references" / "R4"
pytestmark = pytest.mark.skipif(not R4.is_dir(), reason="references/R4 no está en este árbol")
METHODS = {"get", "post", "put", "patch", "delete"}


def _r4() -> dict[str, Any]:
    return yaml.safe_load((R4 / "contracts" / "openapi.v0.draft.yaml").read_text("utf-8"))  # type: ignore[no-any-return]


def _r3() -> dict[str, Any]:
    return json.loads((ROOT / "docs" / "openapi" / "openapi.json").read_text("utf-8"))  # type: ignore[no-any-return]


def _ops(spec: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (m.upper(), re.sub(r"\{[^}]+\}", "{}", p))
        for p, item in spec["paths"].items()
        for m in item
        if m in METHODS
    }


# ============================================================================== rutas
def test_routes_match_except_the_known_health_path_difference() -> None:
    """33 de 34 operaciones coinciden en método y ruta (ignorando el nombre del parámetro).

    Única diferencia: R4 dibujó ``GET /v1/healthz``; la especificación (README §16 y spec R3 §536)
    fija ``GET /healthz`` (sin prefijo, público). R3 sigue la especificación.
    """
    o4, o3 = _ops(_r4()), _ops(_r3())
    assert o4 - o3 == {("GET", "/v1/healthz")}
    assert o3 - o4 == {("GET", "/healthz")}
    assert len(o4 & o3) == 33


def test_all_paths_are_under_v1_except_healthz() -> None:
    assert {p for _, p in _ops(_r3()) if not p.startswith("/v1/")} == {"/healthz"}


# ============================================================================== enums
@pytest.mark.parametrize(
    "enum_cls",
    [
        c
        for c in vars(mirror).values()
        if isinstance(c, type) and issubclass(c, StrEnum) and c is not StrEnum
    ],
)
def test_r4_draft_enums_equal_the_r3_mirror_of_the_spec(enum_cls: type[StrEnum]) -> None:
    """Las etiquetas del borrador de R4 deben ser las de la especificación (espejo de R3)."""
    schemas = _r4()["components"]["schemas"]
    if enum_cls.__name__ not in schemas:
        pytest.skip(f"R4 no define {enum_cls.__name__}")
    values = {v for v in schemas[enum_cls.__name__]["enum"] if v is not None}
    assert values == {m.value for m in enum_cls}, enum_cls.__name__


def test_shared_openapi_enums_are_identical() -> None:
    s4, s3 = _r4()["components"]["schemas"], _r3()["components"]["schemas"]
    common = [n for n in s4 if n in s3 and "enum" in s4[n] and "enum" in s3[n]]
    assert {"JobStatus", "PropertyStatus", "AdaptationMode"} <= set(common)
    for name in common:
        assert set(s4[name]["enum"]) == set(s3[name]["enum"]), name


# ======================================================================== DTO compartidos
def test_login_response_carries_everything_the_r4_session_needs() -> None:
    s4, s3 = _r4()["components"]["schemas"]["Session"], _r3()["components"]["schemas"]
    token = s3["TokenResponse"]
    assert set(s4["required"]) <= set(token["required"]) | {"expires_in", "role"}
    assert set(s4["properties"]) <= set(token["properties"])  # incluye expires_in y role


def test_problem_details_shape_is_compatible() -> None:
    p4 = _r4()["components"]["schemas"]["Problem"]
    p3 = _r3()["components"]["schemas"]["ProblemDetail"]
    assert set(p4["properties"]) == set(p3["properties"])
    assert set(p4["required"]) <= set(p3["required"])  # R3 emite siempre todo lo que R4 exige


def test_job_dto_is_a_subset_of_what_r3_returns() -> None:
    j4 = _r4()["components"]["schemas"]["Job"]
    j3 = _r3()["components"]["schemas"]["JobOut"]
    assert set(j4["properties"]) <= set(j3["properties"])
    assert set(j4["required"]) <= set(j3["required"])


def test_provenance_info_field_names_match_the_spec_and_r4() -> None:
    """README §15 `ProvenanceInfo`: R4 y R3 usan los mismos nombres (R3 añade ip_id/indicator_code/unit)."""
    p4 = _r4()["components"]["schemas"]["ProvenanceInfo"]
    p3 = _r3()["components"]["schemas"]["ProvenanceOut"]
    assert set(p4["properties"]) <= set(p3["properties"])
    assert set(p4["required"]) <= set(p3["required"])
    assert set(p3["properties"]) - set(p4["properties"]) == {"ip_id", "indicator_code", "unit"}
    s4 = _r4()["components"]["schemas"]["SourceRef"]["properties"]
    s3 = _r3()["components"]["schemas"]["SourceOut"]["properties"]
    assert set(s4) <= set(s3)


def test_pdf_download_is_declared_as_application_pdf_only() -> None:
    for spec, path in ((_r3(), "/v1/reports/{id}/pdf"), (_r4(), "/v1/reports/{id}/pdf")):
        resp = spec["paths"][path]["get"]["responses"]["200"]
        assert set(resp["content"]) == {"application/pdf"}


# ----- diferencias de contrato que NO se resuelven aquí (decisión de equipo): se dejan fijadas ----
def test_known_open_contract_differences_are_pinned() -> None:
    """Cada diferencia es una decisión pendiente (docs/auditoria, C-03…C-06). Si cambia, revisar."""
    o4 = _r4()["paths"]
    o3 = _r3()["paths"]
    # C-03: cancelar un trabajo. R4 espera 204 sin cuerpo; R3 devuelve 200 + el trabajo cancelado.
    assert set(o4["/v1/jobs/{id}"]["delete"]["responses"]) >= {"204"}
    assert "200" in o3["/v1/jobs/{id}"]["delete"]["responses"]
    # C-04: listados. R3 pagina con Page[T] (spec R3 §489); R4 usa arreglos desnudos en varios.
    zones4 = o4["/v1/zones"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    zones3 = o3["/v1/zones"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert zones4.get("type") == "array" and "Page" in zones3["$ref"]
    # C-05: respuesta de la carga de CSV. R4 espera 200 {accepted, errors}; R3 devuelve 200 con
    # conteos, o 422 problem+json con errors[{loc,msg,code}] (todo o nada).
    assert "SoilUploadResult" in _r4()["components"]["schemas"]
    row_err = _r4()["components"]["schemas"]["SoilRowError"]
    assert set(row_err["properties"]) == {"row", "column", "message"}
    assert "422" in o3["/v1/parcels/{id}/soil-samples"]["post"]["responses"]


# ================================================================ plantilla del informe (R4)
TEMPLATES = R4 / "apps" / "api" / "templates"
H64 = "a" * 64


class _Labels(dict[str, Any]):
    """Etiquetas de PRUEBA: cualquier clave ausente devuelve su nombre. No son textos reales."""

    def __missing__(self, key: str) -> str:
        return f"«{key}»"


def _context(privacy: str = "public", strategy_name: str = "S") -> dict[str, Any]:
    return {
        "labels": _Labels(privacy_names={"internal": "interno", "public": "público"}),
        "report": {
            "run_id": "00000000-0000-0000-0000-000000000000",
            "privacy_level": privacy,
            "code_version": "test",
            "region_config_hash": H64,
            "catalog_hash": H64,
            "data_hash": H64,
            "params_hash": H64,
            "seed": 1,
        },
        "mode": {"label_text": "indicador_exposicion_climatica", "reasons": ["prueba"]},
        "provisional": True,
        "synthetic_fixture": True,
        "summary_es": "DOBLE DE PRUEBA <script>x</script>",
        "summary_en": "TEST DOUBLE",
        "strategies": [
            {
                "name": strategy_name,
                "freq_critical": "1/2",
                "severity_p90": "1",
                "severity_cvar90": "2",
                "worst_year": 2020,
                "n_valid": 1,
                "n_expected": 2,
                "evidence": "C",
            }
        ],
        "ranking": {
            "status": "ok",
            "rows": [{"name": "S", "total": "0.5"}],
            "weights": {"agua": 0.25},
            "weight_coverage": "1.0",
            "stability": {"flag": "stable", "flag_text": "estable", "conflicts": ["c"]},
        },
        "limitations": ["l"],
        "missing_data": [],
        "field_conditions": [],
        "annex": {
            "methodology": "m",
            "assumptions": ["a"],
            "sources": [
                {"product_name": "p", "institution": "i", "version": None, "is_nasa": False}
            ],
            "indicators": [
                {"label": "x", "evidence": None, "provenance": "modelado", "method": "m"}
            ],
            "scenarios": [],
            "cycles": [],
            "references": [],
        },
    }


def test_r4_template_renders_in_the_restricted_environment_and_inlines_its_css() -> None:
    html = render_template_pack(
        "report_es.html.j2", _context(), privacy_level="public", templates_dir=TEMPLATES
    )
    assert "<style>" in html and 'href="report.css"' not in html
    assert not re.findall(r'(?:href|src)="[^"]+"', html), "no deben quedar recursos externos"
    assert "&lt;script&gt;" in html and "<script>" not in html  # autoescape
    assert 'class="summary-en"' not in html  # locale es: sin resumen en inglés


def test_r4_bilingual_variant_adds_the_english_summary() -> None:
    html = render_template_pack(
        "report_es_en.html.j2", _context(), privacy_level="public", templates_dir=TEMPLATES
    )
    assert 'class="summary-en"' in html and "TEST DOUBLE" in html


def test_r4_template_missing_variable_fails_loudly_never_silently() -> None:
    ctx = _context()
    del ctx["ranking"]
    from jinja2 import UndefinedError

    with pytest.raises(UndefinedError):
        render_template_pack(
            "report_es.html.j2", ctx, privacy_level="public", templates_dir=TEMPLATES
        )


def test_public_report_with_a_coordinate_is_refused() -> None:
    ctx = _context(strategy_name="parcela en 14.123456, -89.654321")
    with pytest.raises(PublicReportPrivacyError):
        render_template_pack(
            "report_es.html.j2", ctx, privacy_level="public", templates_dir=TEMPLATES
        )


# ---- el incrustado de CSS no abre la puerta a recursos externos ni a rutas arbitrarias ----------
def test_inline_stylesheet_rejects_paths_and_dangerous_css(tmp_path: Path) -> None:
    (tmp_path / "ok.css").write_text("p{color:#000}", encoding="utf-8")
    (tmp_path / "bad.css").write_text("p{background:url(http://evil.example/x)}", encoding="utf-8")
    (tmp_path / "imp.css").write_text('@import "http://evil.example/x.css";', encoding="utf-8")
    (tmp_path / "brk.css").write_text("p{} </style><script>x</script>", encoding="utf-8")
    assert "<style>p{color:#000}</style>" in inline_local_stylesheets(
        '<link rel="stylesheet" href="ok.css">', tmp_path
    )
    for name in ("bad.css", "imp.css", "brk.css", "missing.css"):
        with pytest.raises(ReportRenderError):
            inline_local_stylesheets(f'<link rel="stylesheet" href="{name}">', tmp_path)
    # nombres con ruta o URL no coinciden con el patrón: el <link> queda intacto y WeasyPrint lo
    # denegará (política «solo data:»); nunca se lee fuera de la carpeta
    for href in ("../conftest.css", "/etc/passwd.css", "http://evil.example/x.css", "a/b.css"):
        tag = f'<link rel="stylesheet" href="{href}">'
        assert inline_local_stylesheets(tag, tmp_path) == tag


@needs_pdf
def test_r4_template_pdf_keeps_its_stylesheet_and_a4_page_size() -> None:
    """Sin incrustar el CSS, WeasyPrint (sin base_url) descarta ``report.css`` EN SILENCIO y el PDF
    sale en tamaño por defecto (Carta). Con R3 incrustándolo, se respeta ``@page { size: A4 }``."""
    from pypdf import PdfReader

    html = render_template_pack(
        "report_es.html.j2", _context(), privacy_level="public", templates_dir=TEMPLATES
    )
    guard = FetchGuard()
    pdf = html_to_pdf(html, guard)
    assert pdf.startswith(b"%PDF") and guard.denied == []
    box = PdfReader(io.BytesIO(pdf)).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (595, 842)  # A4 en puntos
