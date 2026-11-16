"""Suelo y VoI (T-P09, T-P10), Modo B (T-P15), gating e integración de la fachada."""
from dataclasses import replace

import numpy as np
import pytest

from conftest import make_catalogs, make_region, simple_strategy, synthetic_series
from milpa_core.config import VoiConfig
from milpa_core.crops import PhTolerance
from milpa_core.dto import rank_response_dto, run_summary_dto
from milpa_core.enums import Criterion, Evidence, Mode, PropertyStatus, RankingStatus, VoiApplicability, VoiOutcome
from milpa_core.facade import make_context, rank, run_analysis, soil_voi
from milpa_core.gating import GatingConfig, decide_mode
from milpa_core.planting import heatmap_cycle, heatmap_strategy
from milpa_core.rootzone import simulate_bucket
from milpa_core.serialize import to_jsonable
from milpa_core.soil import InitialCondition, PropertyValue, SoilContext, from_csv_row
from milpa_core.strategy import Component, Strategy, StrategyCycle
from milpa_core.enums import WindowMode


def strategies():
    return [simple_strategy("S1"), simple_strategy("S2", "maiz_largo"),
            Strategy("S3", "milpa", (StrategyCycle(1, "primera", (Component("maiz_t", "principal", 0.6),
                                                                  Component("frijol_t", "acompanante", 0.4, 10)),
                                                   WindowMode.CANDIDATE_DATES),))]


# ---------------------------------------------------------------- T-P10

def test_tp10_property_without_value_is_never_measured():
    ctx = from_csv_row({"ph": 6.1, "om_pct": None})
    assert ctx.property("ph").status is PropertyStatus.MEDIDO
    assert ctx.property("om_pct").status is PropertyStatus.DESCONOCIDO
    assert PropertyValue("ph", PropertyStatus.MEDIDO, None, "agua").status is PropertyStatus.DESCONOCIDO
    assert PropertyValue("ph", PropertyStatus.MEDIDO, 6.0, None).status is PropertyStatus.DESCONOCIDO  # sin método
    assert PropertyValue("ph", PropertyStatus.MEDIDO, 6.0, "agua", age_years=9, max_age_years=5).status is PropertyStatus.DESACTUALIZADO


# ---------------------------------------------------------------- T-P15

def test_tp15_bucket_bounds_and_mass_balance():
    rng = np.random.default_rng(5)
    for _ in range(100):
        n = 120
        p = np.where(rng.uniform(size=n) < 0.4, rng.gamma(0.9, 12, n), 0.0)
        et0 = rng.uniform(3, 6, n)
        kc = np.linspace(0.3, 1.2, n)
        zr = np.linspace(0.2, 1.0, n)
        awc, zs, pf = rng.uniform(80, 200), rng.uniform(0.4, 1.5), rng.uniform(0.3, 0.6)
        dr0 = rng.uniform(0, awc * 0.2 * 0.5)
        b = simulate_bucket(p, et0, kc, zr, awc, zs, pf, dr0)
        assert np.all(b.dr_mm >= -1e-9) and np.all(b.dr_mm <= b.taw_mm + 1e-9)
        assert np.all((b.ks >= 0) & (b.ks <= 1))
        prev = np.concatenate([[dr0], b.dr_mm[:-1]])
        resid = prev - b.dr_mm - (p - b.eta_mm - b.dp_mm)
        unclipped = b.dr_mm < b.taw_mm - 1e-9
        assert np.allclose(resid[unclipped], 0.0, atol=1e-9)


# ---------------------------------------------------------------- gating

def test_gating_mode_a_lists_missing_and_mode_b_when_complete():
    cat = make_catalogs()
    d = decide_mode(SoilContext(), strategies(), cat, GatingConfig())
    assert d.mode is Mode.EXPOSURE and {"awc", "effective_depth", "initial_condition"} <= set(d.reasons)
    vs = {k: replace(v, root_citation="FAO-56 T22", p_citation="FAO-56 T22") for k, v in cat.varieties.items()}
    cat2 = replace(cat, varieties=vs)
    soil = SoilContext({"awc_mm_m": PropertyValue("awc_mm_m", PropertyStatus.MEDIDO, 140, "lab"),
                        "effective_depth": PropertyValue("effective_depth", PropertyStatus.DECLARADO, 0.8)},
                       InitialCondition(0.0, "supuesto declarado"))
    d2 = decide_mode(soil, strategies(), cat2, GatingConfig())
    assert d2.mode is Mode.ROOT_ZONE and not d2.reasons
    # estimado sin PTF aceptada no habilita Modo B
    soil3 = replace(soil, properties={**soil.properties, "awc_mm_m": PropertyValue("awc_mm_m", PropertyStatus.ESTIMADO, 140, "soilgrids")})
    assert decide_mode(soil3, strategies(), cat2, GatingConfig()).mode is Mode.EXPOSURE


def test_mode_b_runs_end_to_end():
    cat = make_catalogs()
    vs = {k: replace(v, root_citation="c", p_citation="c") for k, v in cat.varieties.items()}
    from milpa_core.crops import Threshold
    from milpa_core.enums import ThresholdMetric
    th = cat.thresholds + (Threshold("maiz", "MID", ThresholdMetric.STRESS_DAYS_EQUIV, 5.0, 3.0, 8.0, mode=Mode.ROOT_ZONE, unit="días"),)
    cat2 = replace(cat, varieties=vs, thresholds=th)
    soil = SoilContext({"awc_mm_m": PropertyValue("awc_mm_m", PropertyStatus.MEDIDO, 140, "lab"),
                        "effective_depth": PropertyValue("effective_depth", PropertyStatus.DECLARADO, 0.8)},
                       InitialCondition(0.0, "supuesto declarado"))
    ctx = make_context(make_region(), cat2, synthetic_series(), [simple_strategy("S1")], soil)
    run = run_analysis(ctx)
    assert run.decision.mode is Mode.ROOT_ZONE
    assert all(r.mode is Mode.ROOT_ZONE for r in run.cycle_results)
    assert any(r.stress_days is not None for r in run.cycle_results)


# ---------------------------------------------------------------- integración + VoI

def _ctx(soil=None, cat=None):
    return make_context(make_region(), cat or make_catalogs(), synthetic_series(), strategies(), soil)


def test_facade_end_to_end_and_dtos():
    ctx = _ctx()
    run = run_analysis(ctx)
    assert run.decision.mode is Mode.EXPOSURE
    assert {r.strategy for r in run.strategy_risk} == {"S1", "S2", "S3"}
    hc = heatmap_cycle(list(run.cycle_results), "S1", 1)
    assert len(hc["state"]) == len(hc["years"]) and len(hc["state"][0]) == len(hc["plant_md"])
    hs = heatmap_strategy(list(run.strategy_risk), "S1")
    assert hs["aggregation_rule"] == "any/sum"
    w = {Criterion.WATER: 0.5, Criterion.SOIL: 0.5, Criterion.FOOD: 0.0, Criterion.INCOME: 0.0}
    r, extra = rank(ctx, run, w)
    assert r.status is RankingStatus.OK
    from milpa_core.ranking import rank_stability
    from milpa_core.config import StabilityConfig
    dto = rank_response_dto(r, rank_stability(r, StabilityConfig()), extra)
    assert dto["stability"]["interpretation_es"]
    summ = run_summary_dto(run, ctx.strategies)
    # ningún número de presentación fuera de Indicator en water_inputs
    for s in summ["strategies"]:
        for ind in s["water_inputs"].values():
            assert {"value", "unit", "provenance"} <= set(ind) and ind["provenance"]["evidence_rule"]
            assert ind["label"] == "indicador_exposicion_climatica"
    to_jsonable(run)


PH = {"maiz": PhTolerance("maiz", 4.5, 5.5, 7.5, 8.5, "agua", Evidence.B, "cita"),
      "frijol": PhTolerance("frijol", 5.5, 6.0, 7.0, 7.5, "agua", Evidence.B, "cita")}


def test_voi_applicability_paths_and_tp09():
    w = {Criterion.WATER: 0.5, Criterion.SOIL: 0.5, Criterion.FOOD: 0.0, Criterion.INCOME: 0.0}
    measured = SoilContext({"ph": PropertyValue("ph", PropertyStatus.MEDIDO, 6.2, "agua")})
    ctx = _ctx(measured)
    run = run_analysis(ctx)
    r, _ = rank(ctx, run, w)
    v = soil_voi(ctx, run, r, w)
    assert v.applicability is VoiApplicability.ALREADY_MEASURED and v.outcome is None and not v.lab_recommended
    # desconocido, sin rango → insufficient_info
    ctx = _ctx()
    run = run_analysis(ctx)
    r, _ = rank(ctx, run, w)
    v = soil_voi(ctx, run, r, w)
    assert v.outcome is VoiOutcome.INSUFFICIENT_INFO and not v.lab_recommended
    # estimado con p05–p95, sin matriz → insufficient_info (falta matriz)
    est = SoilContext({"ph": PropertyValue("ph", PropertyStatus.ESTIMADO, 6.0, "soilgrids", p05=4.8, p95=7.2)})
    ctx = _ctx(est)
    run = run_analysis(ctx)
    r, _ = rank(ctx, run, w)
    v = soil_voi(ctx, run, r, w)
    assert v.outcome is VoiOutcome.INSUFFICIENT_INFO and "matriz" in v.rationale_es
    # con matriz → evaluable; frijol excluido a pH bajo → la milpa cae
    ctx = _ctx(est, replace(make_catalogs(), ph_tolerance=PH))
    run = run_analysis(ctx)
    r, _ = rank(ctx, run, w)
    v = soil_voi(ctx, run, r, w, VoiConfig(n_hyp=5))
    assert v.applicability is VoiApplicability.EVALUABLE and v.outcome in (VoiOutcome.RANKING_STABLE, VoiOutcome.RANKING_SENSITIVE)
    assert v.lab_recommended == (v.outcome is VoiOutcome.RANKING_SENSITIVE)
    for h in v.hypotheticals:  # T-P09
        assert h.label == "valor hipotético, no medido" and h.status != "medido"
    assert any("S3" in h.excluded for h in v.hypotheticals)
