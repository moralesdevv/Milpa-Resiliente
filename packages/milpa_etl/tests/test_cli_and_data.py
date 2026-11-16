"""milpa_etl (R1) integrado en la raíz: CLI, catálogos y paquete de demostración. Sin red ni BD."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from milpa_etl import cli

ROOT = Path(__file__).resolve().parents[3]


def test_selftest_of_r1_passes_through_the_unified_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["selftest"]) == 0
    assert "24/24 pruebas OK" in capsys.readouterr().out


def test_unknown_subcommand_is_an_error_not_a_silent_success() -> None:
    assert cli.main(["fetch", "nada"]) == 2
    assert cli.main(["inventado"]) == 2


def test_catalog_validation_sandbox_passes_and_production_fails_on_pending(
    capsys: pytest.CaptureFixture[str],
) -> None:
    crops = str(ROOT / "catalogs" / "crops.yaml")
    assert cli.main(["check-catalog", crops, "--mode", "sandbox"]) == 0
    capsys.readouterr()
    assert cli.main(["check-catalog", crops, "--mode", "production"]) == 2  # P9: sin cita no hay umbral


def test_catalogs_keep_every_agronomic_parameter_pending() -> None:
    """P9: ningún valor agronómico inventado (Kc, fenología, umbrales, variedades)."""
    import yaml

    data = yaml.safe_load((ROOT / "catalogs" / "crops.yaml").read_text(encoding="utf-8"))
    assert data["status"] == "sandbox"
    allowed = {"code", "name_es", "name_en", "scientific_name", "family", "is_legume"}
    allowed |= {"fixes_n_conditions", "varieties"}
    for crop in data["crops"]:
        assert crop["varieties"] == [] and set(crop) <= allowed
    region = yaml.safe_load(
        (ROOT / "regions" / "pilot_corredor_seco.yaml").read_text(encoding="utf-8")
    )
    assert region["agri_year_start"] == "pending"


def test_frozen_demo_package_has_no_personal_data_or_coordinates() -> None:
    demo = ROOT / "data" / "demo"
    if not demo.is_dir():
        pytest.skip("data/demo no existe: ejecutar `milpa-etl build-demo`")
    assert cli.main(["scan-privacy", str(demo)]) == 0
    expected = json.loads((demo / "EXPECTED.json").read_text(encoding="utf-8"))
    leame = (demo / "LEEME.txt").read_text(encoding="utf-8")
    assert expected["label"] == "datos sintéticos" and "SINTÉTICOS" in leame


def test_r1_soil_fixtures_are_validated_by_r1_own_loader_without_a_database() -> None:
    from milpa_etl.loaders import soil_fixture

    fixtures = Path(__file__).parent / "fixtures"
    _digest, rows, errors = soil_fixture.prepare(fixtures / "suelo.csv", "P-014")
    assert errors == [] and len(rows) == 1
    _d, _r, bad = soil_fixture.prepare(fixtures / "suelo_invalido_p014.csv", "P-014")
    assert len(bad) >= 6  # R1 rechaza sus filas inválidas
