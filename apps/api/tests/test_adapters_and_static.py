"""Adaptadores: contrato de la fachada de milpa_core, traducción de errores y estáticos de R4."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from api.adapters.errors import EngineDomainError, translate_engine_error
from api.adapters.milpa_core import (
    DOCUMENTED_FACADE,
    MilpaCoreEngine,
    check_core_contract,
    import_core,
)
from api.adapters.not_integrated import (
    NotIntegratedEngine,
    NotIntegratedEvidence,
    NotIntegratedIngest,
)
from api.adapters.ports import RunRef
from api.adapters.registry import load_ports
from api.config import Settings
from api.errors import DependencyNotIntegrated, ErrorCode
from api.jobs.dispatch import NullDispatcher
from api.main import create_app
from testkit import JWT_SECRET_TEST


def fake_core(**overrides: Any) -> types.ModuleType:
    """MÓDULO DE PRUEBA con las firmas documentadas (NO es R2 y no calcula nada)."""
    mod = types.ModuleType("milpa_core")
    for name, params in DOCUMENTED_FACADE.items():
        ns: dict[str, Any] = {}
        exec(f"def {name}({', '.join(params)}):\n    return None", ns)  # noqa: S102
        setattr(mod, name, ns[name])
    for k, v in overrides.items():
        setattr(mod, k, v)
    return mod


def a_run() -> RunRef:
    return RunRef(uuid4(), uuid4(), None, "a" * 64, "b" * 64, "c" * 64, "v", 1)


def test_without_milpa_core_everything_is_not_integrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "milpa_core", None)  # simula el paquete ausente
    assert import_core() is None
    rep = check_core_contract()
    assert not rep.ok and not rep.package_present and "pendiente de R2" in rep.problems[0]
    ports = load_ports()
    assert isinstance(ports.engine, NotIntegratedEngine) and not ports.engine.is_available()
    assert isinstance(ports.evidence, NotIntegratedEvidence)
    assert isinstance(ports.ingest, NotIntegratedIngest)


def test_installed_milpa_core_matches_the_published_facade() -> None:
    """El paquete real de R2 cumple las firmas publicadas (``DOCUMENTED_FACADE``)."""
    rep = check_core_contract()
    assert rep.package_present and rep.problems == ()


def test_every_engine_operation_raises_typed_dependency_error() -> None:
    eng, run = NotIntegratedEngine(), a_run()
    calls = [
        lambda: eng.run_base_analysis({}),
        lambda: eng.run_scenarios(run, {}),
        lambda: eng.rank(run, {}),
        lambda: eng.soil_voi(run, {}),
        lambda: eng.build_report(run, {}),
        lambda: eng.summary(run, {}),
        lambda: eng.heatmap(run, {}),
        lambda: eng.dekad_chart(run, {}),
        lambda: eng.climate_history(run, {}),
    ]
    for call in calls:
        with pytest.raises(DependencyNotIntegrated) as e:
            call()
        assert e.value.status == 503 and e.value.code == ErrorCode.DEPENDENCY_NOT_INTEGRATED
    with pytest.raises(DependencyNotIntegrated):
        NotIntegratedEvidence().provenance_for_soil(
            kind="medido", property_code="ph", unit="pH", method=None, representativeness=None
        )
    with pytest.raises(DependencyNotIntegrated):
        NotIntegratedIngest().ingest_zone(uuid4())


def test_facade_signature_check_detects_mismatches() -> None:
    assert check_core_contract(fake_core()).ok
    missing = fake_core()
    del missing.rank
    assert "falta la función pública rank" in check_core_contract(missing).problems
    ns: dict[str, Any] = {}
    exec("def rank(contexto, a, b, c):\n    return None", ns)  # noqa: S102
    bad = fake_core(rank=ns["rank"])
    assert any("rank: parámetros" in p for p in check_core_contract(bad).problems)


def test_milpa_core_adapter_refuses_incompatible_package_and_never_fakes_results() -> None:
    with pytest.raises(RuntimeError, match="fachada"):
        MilpaCoreEngine(types.ModuleType("milpa_core"))
    eng = MilpaCoreEngine(fake_core())  # sin rutas de entrada: no disponible, nunca resultados
    assert not eng.is_available()
    with pytest.raises(DependencyNotIntegrated, match="Rutas"):
        eng.climate_history(a_run(), {})  # R2 no publica contrato: no se inventa
    with pytest.raises(DependencyNotIntegrated, match="Rutas"):
        eng.run_base_analysis({"zone_id": str(uuid4())})


def test_registry_selects_adapter_only_for_a_compatible_installed_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "milpa_core", fake_core())
    assert isinstance(load_ports().engine, MilpaCoreEngine)
    monkeypatch.setitem(sys.modules, "milpa_core", types.ModuleType("milpa_core"))
    assert isinstance(load_ports().engine, NotIntegratedEngine)


@pytest.mark.parametrize(
    "name,code",
    [
        ("MixedCycleLengthError", "MIXED_CYCLE_LENGTH"),
        ("MissingThresholdCitation", "MISSING_THRESHOLD_CITATION"),
        ("InsufficientSoilData", "INSUFFICIENT_SOIL_DATA"),
        ("NotComparable", "NOT_COMPARABLE"),
    ],
)
def test_engine_typed_errors_map_to_spec_codes(name: str, code: str) -> None:
    exc = type(name, (Exception,), {})("variedades A y B distintas")
    api = translate_engine_error(exc)
    assert isinstance(api, EngineDomainError) and str(api.code) == code and api.status == 422
    assert "variedades" in api.detail


def test_unknown_engine_errors_are_not_translated() -> None:
    assert translate_engine_error(ValueError("x")) is None


def make_settings(web_dist: Path, tmp: Path) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret=JWT_SECRET_TEST,
        data_dir=tmp / "data",
        web_dist_dir=web_dist,
    )


def test_frontend_static_files_are_served_only_when_dist_exists(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><title>R4</title></html>", encoding="utf-8")
    app = create_app(
        make_settings(dist, tmp_path), dispatcher=NullDispatcher(), recover_on_start=False
    )
    with TestClient(app) as c:
        assert "R4" in c.get("/").text
        assert c.get("/openapi.json").status_code == 200  # la API sigue accesible
    missing = make_settings(tmp_path / "no-existe", tmp_path)
    with TestClient(create_app(missing, dispatcher=NullDispatcher(), recover_on_start=False)) as c:
        assert c.get("/").status_code == 404
