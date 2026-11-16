"""Los catálogos de referencia agronómica no pueden promover valores sin cita (P9, README §11).

Estas pruebas leen los YAML versionados en ``catalogs/r2``; no calculan ciencia. Si alguien añade un
número en un campo que debe seguir ``pending`` o marca como «producción» un valor sin cita, fallan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOGS = ROOT / "catalogs" / "r2"
REFERENCE = CATALOGS / "reference"

# Estados que NO afirman validez local ni uso en producción.
NON_PRODUCTION_STATUSES = {
    "reference_not_production",
    "conflicting_reference_values_pending_technical_resolution",
    "pending_local_validation",
}


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def is_pending(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("pending")


@pytest.mark.contract
@pytest.mark.parametrize("path", sorted(CATALOGS.rglob("*.yaml")), ids=lambda p: p.name)
def test_every_catalog_is_valid_yaml(path: Path) -> None:
    assert load(path) is not None


@pytest.mark.contract
def test_web_sourced_varieties_cite_declared_sources_and_are_not_production() -> None:
    doc = load(REFERENCE / "web_sourced_crops.yaml")
    declared = set(doc["sources"])
    assert (
        doc["catalog_status"].startswith("partial")
        and "pending_local_validation" in (doc["catalog_status"])
    )
    seen = 0
    for crop, body in doc["crops"].items():
        if not isinstance(body, dict):  # parámetros globales aún pendientes (kc_by_stage, ...)
            continue
        varieties = body.get("varieties")
        if is_pending(varieties):  # p. ej. sorgo: sin selección todavía
            continue
        for var in varieties:
            seen += 1
            ids = var.get("source_ids") or [var.get("source_id")]
            assert ids and all(i in declared for i in ids), (
                f"{crop}/{var['id']}: fuente no declarada"
            )
            status = var["status"]
            assert status in NON_PRODUCTION_STATUSES, f"{crop}/{var['id']}: estado {status}"
    assert seen >= 1


@pytest.mark.contract
def test_parameters_without_a_cited_value_stay_pending() -> None:
    """Kc por etapa, grados-día, umbrales críticos y confirmación del piloto no tienen cita: no son números."""
    crops = load(REFERENCE / "web_sourced_crops.yaml")["crops"]
    for key in (
        "kc_by_stage",
        "degree_day_parameters",
        "critical_stage_thresholds",
        "pilot_confirmation",
    ):
        assert key in crops and is_pending(crops[key]), f"{key} no puede tener valor sin cita"
    for crop, body in crops.items():
        if not isinstance(body, dict):
            continue
        for season in ("primera", "postrera"):
            value = body.get("planting_windows", {}).get(season)
            assert value is None or is_pending(value), f"{crop}.planting_windows.{season}"


@pytest.mark.contract
def test_conflicting_source_values_are_kept_side_by_side_not_averaged() -> None:
    doc = load(REFERENCE / "web_sourced_crops.yaml")
    b7 = next(v for v in doc["crops"]["maiz"]["varieties"] if v["id"] == "ICTA_B7")
    by_source = b7["crop_cycle_days_by_source"]
    assert len(set(by_source.values())) > 1, "el conflicto entre fuentes debe conservarse"
    assert "conflicting" in b7["status"]


@pytest.mark.contract
def test_economics_has_no_invented_numbers() -> None:
    doc = load(REFERENCE / "economics.yaml")
    assert doc["status"].startswith("pending")
    for rec in doc["records"]:
        for key, value in rec.items():
            if key == "crop":
                continue
            assert is_pending(value), f"{rec['crop']}.{key}: valor sin fuente ni fecha ({value!r})"


@pytest.mark.contract
def test_evidence_rules_use_the_weakest_input_and_forbid_uncited_production_thresholds() -> None:
    doc = load(REFERENCE / "evidence_rules.yaml")
    assert doc["minimum_propagation"] == "weakest_input_evidence"
    assert doc["no_citation_policy"] == "no_production_threshold"
    levels = {r["indicator"]: r["evidence"] for r in doc["rules"]}
    assert levels["agronomic_catalog_value"] in {"B", "C"}  # nunca A: no es observación
    assert levels["pending_parameter"] == "pending"


@pytest.mark.contract
def test_sandbox_thresholds_without_citation_are_evidence_c() -> None:
    doc = load(CATALOGS / "thresholds.yaml")
    uncited = [t for t in doc["thresholds"] if not t.get("citation")]
    assert uncited, "el catálogo sandbox declara explícitamente que sus umbrales no tienen cita"
    assert all(t["evidence"] == "C" for t in uncited)
