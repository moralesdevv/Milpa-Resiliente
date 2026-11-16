"""Constructor del informe desde el modelo del motor (fixture = salida REAL recortada de milpa_core).

Verifica contenido, tablas, bilingüismo, año parcial 2025, estados vacíos honestos, privacidad pública
y que el PDF generado muestre las mismas cifras que la vista web (mismo ``ReportInput``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from api.reports.contract import ReportInput, RunHashes
from api.reports.from_engine import report_input_from_model
from api.reports.pdf import render_pdf
from api.security.privacy import find_sensitive, iter_strings
from testkit.reports import text_of

MODEL = json.loads(
    (Path(__file__).parent / "fixtures" / "engine_report_model.json").read_text(encoding="utf-8")
)
RUN = UUID("16e09331-37c8-4fa8-8859-708e3bce8a06")
HASHES = RunHashes(
    code_version="test",
    region_config_hash="a" * 64,
    catalog_hash="b" * 64,
    data_hash="c" * 64,
    params_hash="d" * 64,
    seed=42,
)
COVERAGE = [
    {
        "year": y,
        "n_expected": 366 if y % 4 == 0 else 365,
        "n_valid": 273 if y == 2025 else 365 + (y % 4 == 0),
    }
    for y in range(2021, 2026)
]
WINDOW = {"imerg_window": ["2001-01-01", "2025-09-30"], "rain_primary": "IMERG_FINAL_V07"}
SCENARIOS = [
    {
        "scenario": {
            "scenario_id": "T+1_P-10_D+0_Hrh",
            "delta_t_c": 1.0,
            "precip_factor": 0.9,
            "onset_delay_days": 0,
            "humidity_assumption": "constant_rh",
            "adaptation_mode": "none",
        },
        "risk_rows": [
            {
                "strategy": "E1_REF_MAIZ",
                "cohort_freq_critical": {
                    "value": 4.0,
                    "unit": "%",
                    "provenance": {"evidence": "C"},
                },
            }
        ],
    }
]


def build(**over: Any) -> ReportInput:
    kwargs: dict[str, Any] = {
        "zone_name": "Corredor Seco — Jocotán, Chiquimula",
        "run_id": RUN,
        "hashes": HASHES,
        "locale": "es+en",
        "privacy_level": "public",
        "coverage": COVERAGE,
        "data_window": WINDOW,
        "scenarios": SCENARIOS,
    }
    kwargs.update(over)
    return report_input_from_model(MODEL, **kwargs)


def section(data: ReportInput, title: str):  # type: ignore[no-untyped-def]
    return next(s for s in data.sections if s.title_es.startswith(title))


def test_report_has_every_required_block_with_tables() -> None:
    data = build()
    titles = [s.title_es for s in data.sections]
    for expected in (
        "Zona, periodo y cobertura",
        "Estrategias y ciclos",
        "Riesgo por estrategia",
        "Comparación de estrategias",
        "Criterios efectivamente usados",
        "Escenarios sintéticos",
        "Indicadores y procedencia",
        "Decisiones pendientes",
        "Datos faltantes",
    ):
        assert any(t.startswith(expected) for t in titles), expected
    for name in ("Estrategias", "Riesgo", "Comparación", "Criterios", "Indicadores", "Decisiones"):
        assert section(data, name).table is not None, name
    risk = section(data, "Riesgo").table
    assert risk is not None and len(risk.rows) == 7  # E1-E7 una vez cada una
    assert all("%" in row[1] or row[1] == "n/d" for row in risk.rows)  # unidades junto al valor


def test_items_are_parallel_in_both_languages() -> None:
    data = build()
    for s in [*data.sections, *data.annex]:
        assert len(s.items) == len(s.items_en), s.title_es
        assert s.title_en and s.body_en


def test_partial_year_2025_is_marked_with_denominator() -> None:
    data = build()
    cov = section(data, "Zona, periodo")
    assert cov.table is not None
    last = cov.table.rows[-1]
    assert last[0] == "2025" and last[1] == "273" and last[2] == "365" and last[3] == "74.8"
    assert "PARCIAL" in last[4]
    assert any("2025" in x and "PARCIAL" in x and "273 de 365" in x for x in cov.items)
    assert any("2025-09-30" in x for x in cov.items)  # ventana real de IMERG, no inventada
    assert all("Completo" in r[4] for r in cov.table.rows[:-1])


def test_missing_coverage_is_stated_not_invented() -> None:
    cov = section(build(coverage=None, data_window=None), "Zona, periodo")
    assert cov.table is None
    assert any("no afirma una cobertura" in x for x in cov.items)


def test_not_evaluable_criteria_are_explained_not_hidden() -> None:
    data = build()
    crit = section(data, "Criterios").table
    assert crit is not None
    by_name = {row[0].split(" / ")[0]: row for row in crit.rows}
    assert by_name["alimento del hogar"][2].startswith("0 (excluido")
    assert "no evaluable" in by_name["alimento del hogar"][3]
    assert "sin rendimiento de referencia" in by_name["alimento del hogar"][4]
    assert by_name["seguridad hídrica"][2] == "0.50"  # peso efectivo con 2 criterios


def test_no_unknown_or_null_artifacts_in_any_text() -> None:
    import re

    data = build()
    text = "\n".join(iter_strings(data.model_dump(mode="json")))
    for word in ("desconocido", "unknown", "undefined", "[object"):
        assert word not in text.lower(), word
    # restos de Python/JSON como valor mostrado (no la palabra inglesa «none» de una frase)
    assert not re.search(r"\b(None|NaN|nan|null)\b", text)


def test_every_provenance_row_names_a_type_level_and_source() -> None:
    data = build()
    prov = section(data, "Indicadores").table
    assert prov is not None and len(prov.rows) >= 3
    for row in prov.rows:
        assert row[1] and row[2] in {"A", "B", "C"} and row[3]
    assert any("no registra" in x for x in section(data, "Indicadores").items)


def test_scenarios_are_labelled_synthetic_and_compared() -> None:
    data = build()
    sc = section(data, "Escenarios sintéticos")
    assert sc.table is not None and sc.table.rows[0][0] == "T+1_P-10_D+0_Hrh"
    assert any("no son pronósticos" in x for x in sc.items)
    comparison = section(data, "Frecuencia de cohortes críticas por escenario").table
    assert comparison is not None and comparison.rows[0][1] == "4.0 %"
    assert build(scenarios=[]).sections  # sin escenarios: sección honesta
    empty = section(build(scenarios=[]), "Escenarios sintéticos")
    assert empty.table is None and "no hay escenarios" in empty.body_es


def test_spanish_only_locale_has_no_english_headers() -> None:
    data = build(locale="es")
    risk = section(data, "Riesgo").table
    assert risk is not None and "/" not in risk.headers[0]
    assert data.locale == "es" and data.summary_en is None


def test_public_report_is_clean_and_pdf_matches_the_view() -> None:
    data = build()
    assert find_sensitive("\n".join(iter_strings(data.model_dump(mode="json")))) == []
    assert data.internal is None
    pdf = render_pdf(data)
    text = text_of(pdf)
    risk = section(data, "Riesgo").table
    assert risk is not None
    for row in risk.rows:  # las mismas cifras de la vista web aparecen en el PDF
        assert row[1].split()[0] in text
    for needle in ("PARCIAL", "273", "74.8", "Cobertura (%)", "Corredor Seco"):
        assert needle in text, needle
    assert "desconocido" not in text.lower() and "unknown" not in text.lower()


@pytest.mark.parametrize("privacy", ["public", "internal"])
def test_pdf_is_deterministic_for_each_privacy_level(privacy: str) -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    a = render_pdf(build(privacy_level=privacy, now=now))
    b = render_pdf(build(privacy_level=privacy, now=now))
    assert a == b


def test_table_cells_split_unambiguously_into_two_languages() -> None:
    """La vista web elige la mitad ES o EN separando por « / »: ninguna celda puede tener más de una separación."""
    data = build()
    for sec in [*data.sections, *data.annex]:
        if sec.table is None:
            continue
        for cell in [*sec.table.headers, *(c for row in sec.table.rows for c in row)]:
            assert len(cell.split(" / ")) <= 2, (sec.title_es, cell)
