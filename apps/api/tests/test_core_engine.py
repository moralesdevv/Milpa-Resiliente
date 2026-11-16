"""MilpaCoreEngine contra el motor REAL de R2 (milpa_core) y la serie con forma de ``daily.parquet``.

Los datos de estas pruebas son una serie SINTÉTICA ROTULADA generada por ``tools/r2/make_synthetic``
(solo en pruebas aisladas; nunca llega a dashboard/informes). La serie curada real de R1 se usa en
``test_engine_runs_on_real_curated_series`` y la prueba se omite si no está en el árbol.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from api.adapters import core_io
from api.adapters.milpa_core import CoreAssets, MilpaCoreEngine, import_core
from api.adapters.ports import RunRef
from api.errors import DependencyNotIntegrated, NotFound, ValidationFailed

ROOT = Path(__file__).resolve().parents[3]
REGION = ROOT / "regions" / "r2" / "pilot_corredor_seco.yaml"
STRATEGIES = ROOT / "regions" / "r2" / "pilot_corredor_seco.strategies.yaml"
CATALOGS = ROOT / "catalogs" / "r2"
REAL_DAILY = ROOT / "data" / "curated" / "chiquimula_prueba" / "daily.parquet"

pytestmark = pytest.mark.skipif(import_core() is None, reason="milpa_core no instalado")


def _engine(daily: Path) -> MilpaCoreEngine:
    core = import_core()
    assert core is not None
    return MilpaCoreEngine(core, CoreAssets(REGION, STRATEGIES, CATALOGS, lambda _zone: daily))


@pytest.fixture(scope="module")
def synthetic_daily(tmp_path_factory: pytest.TempPathFactory) -> Path:
    sys.path.insert(0, str(ROOT / "tools" / "r2"))
    try:
        from make_synthetic import make  # SINTÉTICO rotulado: solo pruebas aisladas
    finally:
        sys.path.pop(0)
    path = tmp_path_factory.mktemp("synthetic") / "daily.csv"
    make("2021-01-01", "2025-12-31").to_csv(path, index=False)
    return path


def _ref(zone: UUID, payload: dict, run_id: UUID | None = None) -> RunRef:
    run = payload["run"]
    return RunRef(
        run_id or uuid4(),
        zone,
        None,
        run["data_hash"],
        "p" * 64,
        run["region_config_hash"],
        run["code_version"],
        run["seed"],
    )


@pytest.fixture(scope="module")
def base(synthetic_daily: Path) -> tuple[MilpaCoreEngine, UUID, dict, RunRef]:
    eng, zone = _engine(synthetic_daily), uuid4()
    out = dict(eng.run_base_analysis({"zone_id": str(zone), "seed": 0}))
    return eng, zone, out, _ref(zone, out)


def test_base_run_reports_mode_hashes_and_sandbox_flag(base) -> None:
    _eng, _zone, out, _ = base
    run = out["run"]
    assert run["mode"] in {"exposure", "root_zone"} and run["sandbox"] is True
    assert len(run["data_hash"]) == 64 and len(run["region_config_hash"]) == 64
    assert run["code_version"].startswith("milpa_core")
    assert out["summary"]["strategies"], "el resumen debe traer estrategias (DTO de R2)"
    assert any("sandbox" in lim for lim in out["summary"]["limitations"])


def test_base_run_is_deterministic(synthetic_daily: Path) -> None:
    zone = uuid4()
    a = _engine(synthetic_daily).run_base_analysis({"zone_id": str(zone), "seed": 0})
    b = _engine(synthetic_daily).run_base_analysis({"zone_id": str(zone), "seed": 0})
    assert a["run"]["data_hash"] == b["run"]["data_hash"]
    assert a["run"]["region_config_hash"] == b["run"]["region_config_hash"]
    assert a["summary"]["strategies"] == b["summary"]["strategies"]


def test_presentation_dtos_come_from_the_engine(base) -> None:
    eng, _zone, _out, ref = base
    assert eng.summary(ref, {})["scenario"]["scenario_id"] == "BASE"
    heat = eng.heatmap(ref, {})["heatmaps"]
    assert heat and all({"cycle", "strategy"} <= set(v) for v in heat.values())
    assert eng.dekad_chart(ref, {})


def test_rank_and_soil_voi_without_soil_do_not_invent_values(base) -> None:
    eng, _zone, _out, ref = base
    request = {
        "scenario_id": "BASE",
        "adaptation_mode": "none",
        "weights": {"water": 0.4, "soil": 0.2, "food": 0.2, "income": 0.2},
        "missing_policy": "common_support",
        "stability": {"n_samples": 500, "mode": "dirichlet", "seed": 7},
    }
    ranking = eng.rank(ref, request)
    assert ranking["status"] in {"ok", "insufficient"}
    assert ranking["stability"]["seed"] == 7 and ranking["stability"]["n_samples"] == 500
    assert ranking["anchors"]
    voi = eng.soil_voi(ref, {"scenario_id": "BASE", "adaptation_mode": "none"})
    assert voi.get("outcome") is None or voi.get("applicability")  # sin suelo: no hay VoI inventado
    report = eng.build_report(ref, {"scenario_id": "BASE", "stability": {"seed": 1}})
    assert {s["id"] for s in report["sections"]} >= {"resumen", "riesgo"}


def test_scenarios_report_skipped_instead_of_inventing(base) -> None:
    eng, _zone, _out, ref = base
    done = eng.run_scenarios(
        ref, {"scenario_ids": ["T+1_P-10_D+0_Hrh"], "adaptation_modes": ["none"]}
    )
    assert [s["status"] for s in done["scenarios"]] == ["ok"]
    assert eng.summary(ref, {"scenario": "T+1_P-10_D+0_Hrh"})["scenario"]["delta_t_c"] == 1.0
    with pytest.raises(NotFound):
        eng.run_scenarios(ref, {"scenario_ids": ["T+9_P-99_D+0_Hrh"]})
    skipped = eng.run_scenarios(ref, {"scenario_ids": ["BASE"], "adaptation_modes": ["onset_rule"]})
    assert skipped["scenarios"][0]["status"] in {"ok", "skipped"}


def test_engine_rebuilds_a_run_after_cache_loss_and_refuses_changed_inputs(base) -> None:
    eng, zone, _, ref = base
    fresh = _engine(eng._assets.daily_for_zone(zone))  # type: ignore[union-attr]
    assert fresh.summary(ref, {})["scenario"]["scenario_id"] == "BASE"
    with pytest.raises(ValidationFailed, match="cambiaron"):
        _engine(eng._assets.daily_for_zone(zone)).summary(  # type: ignore[union-attr]
            replace(ref, run_id=uuid4(), data_hash="0" * 64), {}
        )


def test_missing_series_is_reported_and_parcel_soil_never_invents_values(tmp_path: Path) -> None:
    eng = _engine(tmp_path / "no-existe.parquet")
    with pytest.raises(DependencyNotIntegrated, match="serie curada"):
        eng.run_base_analysis({"zone_id": str(uuid4()), "seed": 0})
    ctx = core_io.soil_context_from_rows(
        [
            {"property_code": "ph", "status": "desconocido"},
            {
                "property_code": "effective_depth",
                "status": "declarado",
                "d_value": 80,
                "max_age_years": None,
            },
            {"property_code": "awc", "status": "medido", "m_value": 120.0, "method": None},
        ]
    )
    assert ctx.property("ph").value is None and ctx.property("ph").status.value == "desconocido"
    assert abs(ctx.property("effective_depth").value - 0.8) < 1e-9  # cm -> m
    assert ctx.property("awc_mm_m").status.value == "desconocido"  # medido sin método no se acepta


@pytest.mark.skipif(not REAL_DAILY.is_file(), reason="serie curada real de R1 no presente")
def test_engine_runs_on_real_curated_series() -> None:
    out = _engine(REAL_DAILY).run_base_analysis({"zone_id": str(uuid4()), "seed": 0})
    assert out["run"]["curated"]["n_days"] == 1826
    assert out["run"]["curated"]["missing_pct"]["precip_mm"] == 0.0
    parity = out["summary"].get("et0_parity_vs_R1")
    assert parity and parity["mean_abs_diff_mm"] < 0.1  # ET0 del motor vs ET0 de R1


def test_core_io_reindexes_missing_days_as_nan(tmp_path: Path, synthetic_daily: Path) -> None:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(synthetic_daily).drop(index=[10, 11, 12])
    path = tmp_path / "daily.csv"
    df.to_csv(path, index=False)
    series, info = core_io.load_curated_daily(path, None, "2021-01-01", "2025-12-31")
    assert info.n_days == 1826 and np.isnan(series.precip_mm[10:13]).all()


def test_dekad_filter_and_climate_history_on_the_synthetic_series(base) -> None:
    eng, _zone, _out, ref = base
    one = eng.dekad_chart(
        ref,
        {"strategy": "E1_REF_MAIZ", "cohort_year": 2022, "cycle": 1, "plant_date": "2022-05-01"},
    )
    assert one["cohort_year"] == 2022 and one["plant_date"] == "2022-05-01" and one["dekads"]
    with pytest.raises(NotFound):
        eng.dekad_chart(ref, {"strategy": "E1_REF_MAIZ", "cohort_year": 1999, "cycle": 1})
    history = eng.climate_history(ref, {})
    assert [y["year"] for y in history["years"]] == [2021, 2022, 2023, 2024, 2025]
    assert history["years"][0]["precip_mm"]["provenance"]["evidence"] in {"A", "B", "C"}
    assert history["trends"] == []  # 5 años completos (< 10): no se inventa una tendencia


CAMOTAN = ROOT / "data" / "curated" / "camotan_jocotan" / "daily.parquet"


@pytest.mark.skipif(not CAMOTAN.is_file(), reason="serie curada de camotan_jocotan no presente")
def test_25_year_history_reports_descriptive_trends_with_provenance() -> None:
    eng = _engine(CAMOTAN)
    zone = uuid4()
    out = eng.run_base_analysis(
        {"zone_id": str(zone), "seed": 0, "period_start": "2001-01-01", "period_end": "2025-12-31"}
    )
    run = out["run"]
    ref = RunRef(
        uuid4(),
        zone,
        None,
        run["data_hash"],
        "p" * 64,
        run["region_config_hash"],
        run["code_version"],
        0,
        __import__("datetime").date(2001, 1, 1),
        __import__("datetime").date(2025, 12, 31),
    )
    history = eng.climate_history(ref, {})
    assert len(history["years"]) == 25
    trend = next(t for t in history["trends"] if t["variable"] == "precipitation")
    assert trend["change_per_decade"]["unit"] == "mm/decade"
    assert "no significance test" in trend["description_es"]
    # lluvia anual plausible del Corredor Seco oriental (IMERG, tasa por 24 h verificado): cientos a pocos miles de mm
    totals = [
        y["precip_mm"]["value"] for y in history["years"] if y["precip_mm"]["value"] is not None
    ]
    assert min(totals) > 800 and max(totals) < 3000
