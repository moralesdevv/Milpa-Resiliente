"""Escenarios (T-P05, T-P11, T-P17), ranking (T-P06, T-P12, T-P13), estabilidad (T-P16), evidencia (T-P14)."""
from dataclasses import replace

import numpy as np
import pytest

from conftest import curated, make_catalogs, make_region, simple_strategy, synthetic_series
from milpa_core.config import OnsetDef, RankingConfig, StabilityConfig
from milpa_core.criteria import CriterionValue
from milpa_core.enums import (CRITERIA, AdaptationMode, Criterion, CriterionStatus, Evidence, HumidityAssumption,
                              IndicatorKind, Label, Provenance, RankingStatus, StabilityFlag, export_sql)
from milpa_core.errors import IndicatorContractError, ScenarioNotApplicable
from milpa_core.facade import make_context, run_analysis
from milpa_core.provenance import IndicatorBuilder, ProvenanceInfo, min_evidence
from milpa_core.ranking import rank, rank_stability, sample_weights
from milpa_core.scenarios import ScenarioDef, apply_scenario, delay_rain_onset, detect_onset, standard_grid

ONSET = OnsetDef("04-15", 20.0, 3, 10, 30, 1.0, None)


# ---------------------------------------------------------------- grilla

def test_grid_45_with_roles_and_grammar():
    g = standard_grid()
    assert len(g) == 45 and len({s.scenario_id for s in g}) == 45
    roles = [s.grid_role for s in g]
    assert roles.count("baseline") == 1 and roles.count("primary_grid") == 26 and roles.count("humidity_sensitivity") == 18
    assert "BASE" in {s.scenario_id for s in g} and "T+2_P-20_D+20_Hea" in {s.scenario_id for s in g}
    with pytest.raises(ValueError):
        ScenarioDef("x", 1.0, 1.0, 0, HumidityAssumption.NOT_APPLICABLE)


# ---------------------------------------------------------------- T-P05

def test_tp05_delay_invariants():
    rng = np.random.default_rng(0)
    for _ in range(200):
        n = int(rng.integers(60, 400))
        p = np.where(rng.uniform(size=n) < 0.4, rng.gamma(0.9, 10, n), 0.0)
        p[rng.choice(n, 3, replace=False)] = np.nan
        t0 = int(rng.integers(0, n // 2))
        d = int(rng.integers(0, n // 4))
        out, dropped = delay_rain_onset(p, t0, d)
        assert np.array_equal(out[:t0], p[:t0], equal_nan=True)
        assert np.all(out[t0:t0 + d] == 0.0)
        assert np.nansum(out) + dropped == pytest.approx(np.nansum(p))
        if d == 0:
            assert np.array_equal(out, p, equal_nan=True)
        d1, d2 = int(rng.integers(0, 10)), int(rng.integers(0, 10))
        if t0 + d1 + d2 < n:
            a, _ = delay_rain_onset(delay_rain_onset(p, t0, d1)[0], t0, d2)
            b, _ = delay_rain_onset(p, t0, d1 + d2)
            assert np.array_equal(a, b, equal_nan=True)


def test_delay_exceeding_series_raises():
    with pytest.raises(ScenarioNotApplicable):
        delay_rain_onset(np.ones(10), 5, 5)


def test_detect_onset_simple():
    p = np.zeros(200)
    p[100:103] = 10.0
    p[103:200:3] = 5.0
    assert detect_onset(p, 0, ONSET) == 100


# ---------------------------------------------------------------- T-P11 / T-P17

def _ctx(**rk):
    region = make_region(onset=ONSET, adaptation_lag_days=0, **rk)
    return make_context(region, make_catalogs(), synthetic_series(), [simple_strategy("S1"), simple_strategy("S2", "maiz_largo")])


def test_tp17_dT0_et0_equals_base():
    ctx = _ctx()
    sc = apply_scenario(ctx.climate, ctx.base_climate, ScenarioDef("T+0_P-10_D+0_Hna", 0, 0.9, 0), ctx.region)
    assert np.allclose(sc.et0_mm, ctx.base_climate.et0_mm, equal_nan=True)


def test_tp11_scenario_does_not_modify_baseline():
    ctx = _ctx()
    before = {k: np.array(v) for k, v in ctx.base_climate.pef_day.items()}
    p0 = np.array(ctx.climate.precip_mm)
    base = run_analysis(ctx)
    h0 = [(r.strategy, r.cohort_year, r.anchor_md, r.state, r.severity_mm) for r in base.cycle_results]
    for sc in (ScenarioDef("T+2_P-20_D+20_Hrh", 2, 0.8, 20, HumidityAssumption.CONSTANT_RH),):
        run_analysis(ctx, sc, AdaptationMode.ONSET_RULE)
    again = run_analysis(ctx)
    assert h0 == [(r.strategy, r.cohort_year, r.anchor_md, r.state, r.severity_mm) for r in again.cycle_results]
    assert np.array_equal(p0, ctx.climate.precip_mm, equal_nan=True)
    for k in before:
        assert np.array_equal(before[k], ctx.base_climate.pef_day[k], equal_nan=True)
    with pytest.raises(ValueError):
        ctx.climate.precip_mm[0] = 1.0  # arrays de solo lectura


def test_warming_raises_et0_and_humidity_assumptions_order():
    ctx = _ctx()
    rh = apply_scenario(ctx.climate, ctx.base_climate, ScenarioDef("T+2_P+0_D+0_Hrh", 2, 1, 0, HumidityAssumption.CONSTANT_RH), ctx.region)
    ea = apply_scenario(ctx.climate, ctx.base_climate, ScenarioDef("T+2_P+0_D+0_Hea", 2, 1, 0, HumidityAssumption.CONSTANT_EA), ctx.region)
    b = np.nansum(ctx.base_climate.et0_mm)
    assert np.nansum(rh.et0_mm) > b and np.nansum(ea.et0_mm) > np.nansum(rh.et0_mm)  # constant_rh es el conservador
    assert rh.et0_prov.evidence is Evidence.C  # tope C en escenarios


def test_delay_disabled_without_onset_definition():
    region = make_region()
    ctx = make_context(region, make_catalogs(), synthetic_series(), [simple_strategy()])
    with pytest.raises(ScenarioNotApplicable):
        run_analysis(ctx, ScenarioDef("T+0_P+0_D+10_Hna", 0, 1, 10))


# ---------------------------------------------------------------- ranking

def cv(c, v, st=CriterionStatus.EVALUABLE, ev=Evidence.C):
    return CriterionValue(c, st, v, ev if st is not CriterionStatus.NOT_EVALUABLE else None)


def table(rows):
    return {s: {c: (cv(c, rows[s][c]) if rows[s].get(c) is not None else cv(c, None, CriterionStatus.NOT_EVALUABLE))
                for c in CRITERIA} for s in rows}


W = {Criterion.WATER: 0.4, Criterion.SOIL: 0.3, Criterion.FOOD: 0.2, Criterion.INCOME: 0.1}


def test_rank_insufficient_with_one_strategy():
    r = rank(table({"A": {Criterion.WATER: 1}}), W, RankingConfig())
    assert r.status is RankingStatus.INSUFFICIENT


def test_tp12_common_support_same_as_if_criterion_absent():
    rng = np.random.default_rng(1)
    for _ in range(100):
        rows = {s: {c: float(rng.uniform()) for c in CRITERIA} for s in "ABCDE"}
        rows["C"][Criterion.FOOD] = None  # falta en una → sale para todas
        r1 = rank(table(rows), W, RankingConfig())
        rows2 = {s: {c: v for c, v in d.items() if c is not Criterion.FOOD} for s, d in rows.items()}
        w2 = {**W, Criterion.FOOD: 0.0}
        w2 = {k: v / sum(w2.values()) for k, v in w2.items()}
        r2 = rank(table(rows2), w2, RankingConfig())
        assert r1.order == r2.order
        assert Criterion.FOOD not in r1.criteria_used
        assert any(d["decision"] == "criterio_fuera_del_soporte_comun" for d in r1.decision_log)


def test_tp13_constant_criterion_is_neutral():
    rng = np.random.default_rng(2)
    for _ in range(100):
        rows = {s: {c: float(rng.uniform()) for c in CRITERIA} for s in "ABCD"}
        base = rank(table(rows), W, RankingConfig())
        for s in rows:
            rows[s][Criterion.INCOME] = 7.0
        r = rank(table(rows), W, RankingConfig())
        assert all(r.scores[Criterion.INCOME][s] == 0.5 for s in rows)
        assert Criterion.INCOME in r.non_discriminating
        rows2 = {s: {c: v for c, v in d.items() if c is not Criterion.INCOME} for s, d in rows.items()}
        w2 = {**W, Criterion.INCOME: 0.0}
        w2 = {k: v / sum(w2.values()) for k, v in w2.items()}
        assert r.order == rank(table(rows2), w2, RankingConfig()).order
        assert base.status is RankingStatus.OK


def test_unknown_never_zero_and_coverage_rule():
    rows = {"A": {Criterion.WATER: 0.9}, "B": {Criterion.WATER: 0.1}}
    r = rank(table(rows), W, RankingConfig(min_weight_coverage=0.5))
    assert r.status is RankingStatus.INSUFFICIENT and r.partial_table is not None  # 0.4 < 0.5
    r = rank(table(rows), W, RankingConfig(min_weight_coverage=0.3))
    assert r.status is RankingStatus.OK and r.weights_effective == {Criterion.WATER: 1.0}


def test_exclude_incomplete_policy():
    rows = {"A": {c: 0.5 for c in CRITERIA}, "B": {c: 0.6 for c in CRITERIA}, "C": {Criterion.WATER: 1.0}}
    r = rank(table(rows), W, RankingConfig(missing_policy="exclude_incomplete"))
    assert "C" not in r.order and len(r.criteria_used) == 4


def test_tp06_weights_sum_to_one():
    w0 = np.array([0.4, 0.3, 0.2, 0.1])
    for mode in ("dirichlet", "ball"):
        Ws = sample_weights(w0, StabilityConfig(mode=mode, n_samples=1000))
        assert np.allclose(Ws.sum(axis=1), 1.0) and np.all(Ws >= 0)
    rows = {s: {c: float(v) for c, v in zip(CRITERIA, np.random.default_rng(3).uniform(size=4))} for s in "ABC"}
    r = rank(table(rows), W, RankingConfig())
    assert sum(r.weights_effective.values()) == pytest.approx(1.0)


def test_tp16_stability_flags_and_enum_parity():
    rows = {"A": {Criterion.WATER: 1.0, Criterion.SOIL: 0.0}, "B": {Criterion.WATER: 0.0, Criterion.SOIL: 1.0}}
    w = {Criterion.WATER: 0.5, Criterion.SOIL: 0.5, Criterion.FOOD: 0.0, Criterion.INCOME: 0.0}
    base = rank(table(rows), w, RankingConfig(min_weight_coverage=0.5))
    st = rank_stability(base, StabilityConfig(n_samples=2000))
    assert st.flag in (StabilityFlag.UNSTABLE, StabilityFlag.MODERATE) and st.conflicts
    w2 = {Criterion.WATER: 0.9, Criterion.SOIL: 0.1, Criterion.FOOD: 0.0, Criterion.INCOME: 0.0}
    st2 = rank_stability(rank(table(rows), w2, RankingConfig(min_weight_coverage=0.5)), StabilityConfig())
    assert st2.flag is StabilityFlag.STABLE
    assert rank_stability(rank(table({"A": rows["A"]}), w, RankingConfig()), StabilityConfig()).flag is StabilityFlag.INSUFFICIENT
    assert "interpretation_es" in st.__dataclass_fields__ and st.interpretation_es
    sql = export_sql()
    for f in StabilityFlag:
        assert f"'{f.value}'" in sql
    assert len(StabilityFlag) == 4


# ---------------------------------------------------------------- T-P14 / contrato Indicator

def _prov(ev):
    return ProvenanceInfo(Provenance.MODELADO if ev else Provenance.DESCONOCIDO, ev, "rule", "m")


def test_tp14_output_evidence_never_exceeds_min_input():
    rng = np.random.default_rng(4)
    levels = [Evidence.A, Evidence.B, Evidence.C, None]
    for _ in range(300):
        ins = [levels[i] for i in rng.integers(0, 4, size=rng.integers(1, 5))]
        b = IndicatorBuilder("x_mm", "x", "x", "mm", IndicatorKind.CLIMATE_INPUT).from_inputs(*[_prov(e) for e in ins]).rule("r")
        out = b.build(1.0).provenance.evidence
        m = min_evidence(ins)
        if m is None:
            assert out is None
        else:
            assert out.rank <= m.rank


def test_indicator_contract():
    p = _prov(Evidence.B)
    b = IndicatorBuilder("e", "e", "e", "mm", IndicatorKind.EXPOSURE, Label.ROOT_ZONE_BALANCE).from_inputs(p).rule("r")
    with pytest.raises(IndicatorContractError):
        b.build(1.0)
    b = IndicatorBuilder("e", "e", "e", "mm", IndicatorKind.EXPOSURE, Label.EXPOSURE_INDICATOR).from_inputs(p).rule("r")
    with pytest.raises(IndicatorContractError):
        b.build(1.0, provisional=True)
    assert b.build(1.0, provisional=True, reason="umbral sandbox").provisional
