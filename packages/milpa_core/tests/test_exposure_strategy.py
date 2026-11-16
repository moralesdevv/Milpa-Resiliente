"""Modo A, calendario, cohortes y agregación: T-G03, T-G04, T-P01, T-P03, T-P07, T-P08."""
from dataclasses import replace

import numpy as np
import pytest

from conftest import PEFF, curated, make_catalogs, make_region, maize, simple_strategy, synthetic_series
from milpa_core.climate.series import ClimateSeries, derive_climate
from milpa_core.config import RiskConfig
from milpa_core.crops import assert_same_cycle_length, build_calendar
from milpa_core.enums import CellState, PeffMethod, WindowMode
from milpa_core.errors import MixedCycleLengthError, MultipleSweepCycles, StrategyValidationError
from milpa_core.exposure import evaluate_cycle_exposure
from milpa_core.risk import aggregate_cycle, cohort_state
from milpa_core.strategy import Component, Strategy, StrategyCycle, enumerate_cohorts, instantiate_cohort, validate_strategy


def _const_series(p_fn):
    d = np.arange(np.datetime64("2021-01-01"), np.datetime64("2026-01-01"))
    p = np.array([p_fn(x) for x in d], dtype=float)
    n = d.size
    return ClimateSeries(d, np.full(n, 31.0), np.full(n, 20.0), p, np.full(n, 2.0), np.full(n, 20.0), tdew_c=np.full(n, 17.0))


# ---------------------------------------------------------------- calendario

def test_calendar_days_kc_shape():
    v = maize()
    cal = build_calendar(v, np.datetime64("2021-05-01"))
    assert cal.n_days == 125
    assert str(cal.harvest_date) == "2021-09-02"
    assert cal.kc[0] == pytest.approx(0.3) and cal.kc[60] == pytest.approx(1.2)
    assert cal.critical.sum() == 40


def test_mixed_cycle_length_rejected():
    with pytest.raises(MixedCycleLengthError):
        assert_same_cycle_length([maize(), maize("x", (25, 40, 45, 30))])


# ---------------------------------------------------------------- T-G03

def test_tg03_dry_dekad_in_flowering_with_enough_cumulative_is_critical():
    region = make_region(peff_enabled=(PeffMethod.UPPER_BOUND,), primary_peff=PeffMethod.UPPER_BOUND)
    dry = (np.datetime64("2023-07-11"), np.datetime64("2023-07-20"))
    s = _const_series(lambda x: 0.0 if dry[0] <= x <= dry[1] else 10.0)
    clim = derive_climate(s, region.lat_deg, region.elevation_m, region.peff_enabled)
    cat = make_catalogs(thr=15.0, low=10.0, high=20.0, cited=True)
    strat = simple_strategy(window=("05-01", "05-01"))
    ch = instantiate_cohort(strat, 2023, np.datetime64("2023-05-01"), region, cat, s.dates[0], s.dates[-1])
    ci = ch.cycles[0]
    r = evaluate_cycle_exposure(ci, clim, cat, region)
    sl = clim.sl(ci.plant_date, ci.harvest_date)
    assert np.sum(clim.pef_day["upper_bound"][sl]) > np.sum(clim.et0_mm[sl] * ci.components[0].calendar.kc)  # acumulado suficiente
    assert r.state is CellState.CRITICAL
    assert not r.provisional
    # sin la decena seca no es crítico
    s2 = _const_series(lambda x: 10.0)
    clim2 = derive_climate(s2, region.lat_deg, region.elevation_m, region.peff_enabled)
    assert evaluate_cycle_exposure(ci, clim2, cat, region).state is CellState.NON_CRITICAL


def test_missing_threshold_gives_insufficient_data():
    region = make_region()
    cat = replace(make_catalogs(), thresholds=())
    s = synthetic_series()
    clim = curated(s, region)
    ch = enumerate_cohorts(simple_strategy(), region, cat, s.dates[0], s.dates[-1])[0]
    r = evaluate_cycle_exposure(ch.cycles[0], clim, cat, region)
    assert r.state is CellState.INSUFFICIENT_DATA
    assert "provisional_sin_cita" in r.reasons


def test_sandbox_threshold_is_provisional_with_reason():
    region = make_region()
    cat = make_catalogs(cited=False)
    s = synthetic_series()
    ch = enumerate_cohorts(simple_strategy(), region, cat, s.dates[0], s.dates[-1])[0]
    r = evaluate_cycle_exposure(ch.cycles[0], curated(s, region), cat, region)
    assert r.provisional and r.reasons


def test_tp04_missing_rain_makes_cycle_not_evaluable():
    region = make_region()
    s = synthetic_series()
    p = np.array(s.precip_mm)
    p[int((np.datetime64("2022-06-10") - s.dates[0]).astype(int))] = np.nan
    s2 = replace(s, precip_mm=p)
    cat = make_catalogs()
    ch = [c for c in enumerate_cohorts(simple_strategy(), region, cat, s.dates[0], s.dates[-1]) if c.cohort_year == 2022][0]
    r = evaluate_cycle_exposure(ch.cycles[0], curated(s2, region), cat, region)
    assert r.state is CellState.NOT_EVALUABLE


# ---------------------------------------------------------------- T-P01

@pytest.mark.parametrize("method", [m.value for m in PEFF])
def test_tp01_uniform_rain_increase_does_not_raise_exposure(method):
    region = make_region()
    cat = make_catalogs()
    rng = np.random.default_rng(7)
    for seed in range(4):
        s = synthetic_series(seed)
        k = float(rng.uniform(1.0, 3.0))
        s_more = replace(s, precip_mm=np.array(s.precip_mm) * k)
        c0, c1 = curated(s, region), curated(s_more, region)
        for ch in enumerate_cohorts(simple_strategy(), region, cat, s.dates[0], s.dates[-1])[::7]:
            a = evaluate_cycle_exposure(ch.cycles[0], c0, cat, region, method, False)
            b = evaluate_cycle_exposure(ch.cycles[0], c1, cat, region, method, False)
            assert b.severity_mm <= a.severity_mm + 1e-9


# ---------------------------------------------------------------- T-P03 / T-P07

def _results(region=None, cat=None, strat=None):
    region = region or make_region()
    cat = cat or make_catalogs()
    s = synthetic_series()
    clim = curated(s, region)
    strat = strat or simple_strategy()
    out = []
    for ch in enumerate_cohorts(strat, region, cat, s.dates[0], s.dates[-1]):
        for ci in ch.cycles:
            out.append(evaluate_cycle_exposure(ci, clim, cat, region))
    return out


def test_tp03_raising_threshold_does_not_increase_frequency():
    for risk in aggregate_cycle(_results(), RiskConfig()):
        ts = risk.threshold_sensitivity
        assert ts["low"] >= ts["central"] - 1e-9 >= ts["high"] - 2e-9
    freqs = []
    for thr in (30, 45, 60, 75, 90):
        rs = aggregate_cycle(_results(cat=make_catalogs(thr=thr, low=thr, high=thr)), RiskConfig())
        freqs.append(np.mean([r.freq_critical_pct for r in rs]))
    assert all(a >= b - 1e-9 for a, b in zip(freqs, freqs[1:]))


def test_tp07_not_evaluable_cycles_do_not_change_percentiles():
    res = _results()
    base = aggregate_cycle(res, RiskConfig())
    ne = [replace(r, state=CellState.NOT_EVALUABLE, severity_mm=999.0) for r in res[:10]]
    ne = [replace(r, cohort_year=r.cohort_year + 100) for r in ne]
    more = aggregate_cycle(res + ne, RiskConfig())
    for a, b in zip(base, more):
        assert a.stats["severity_p90_mm"] == b.stats["severity_p90_mm"]
        assert a.stats["severity_cvar90_mm"] == b.stats["severity_cvar90_mm"]
        assert a.freq_critical_pct == b.freq_critical_pct
        assert b.n_expected >= a.n_expected


def test_trivalent_cohort_logic():
    C, N, I, E = CellState.CRITICAL, CellState.NON_CRITICAL, CellState.INSUFFICIENT_DATA, CellState.NOT_EVALUABLE
    assert cohort_state([C, E]) is C
    assert cohort_state([N, N]) is N
    assert cohort_state([N, E]) is I
    assert cohort_state([N, I]) is I


# ---------------------------------------------------------------- estrategias (T-P08, T-G04)

def _rotation(cat):
    return Strategy("ROT", "rot", (
        StrategyCycle(1, "primera", (Component("maiz_t"),), WindowMode.CANDIDATE_DATES, fallow_after_days=3),
        StrategyCycle(2, "postrera", (Component("frijol_t"),), WindowMode.RELATIVE_TO_PREVIOUS_HARVEST, rel_lag_days=2),
        StrategyCycle(3, "primera", (Component("maiz_largo"),), WindowMode.FIXED_SEASON_WINDOW, agri_year_offset=1),
    ))


def test_tg04_two_year_rotation_known_dates():
    region, cat = make_region(), make_catalogs()
    s = _rotation(cat)
    validate_strategy(s, cat, region)
    ch = instantiate_cohort(s, 2021, np.datetime64("2021-05-01"), region, cat, np.datetime64("2021-01-01"), np.datetime64("2025-12-31"))
    c1, c2, c3 = ch.cycles
    assert (str(c1.plant_date), str(c1.harvest_date)) == ("2021-05-01", "2021-09-02")
    assert str(c2.plant_date) == "2021-09-08"  # 09-02 + 1 + reposo 3 + lag 2
    assert str(c2.harvest_date) == "2021-12-11"  # 95 días
    assert (str(c3.plant_date), str(c3.harvest_date)) == ("2022-05-01", "2022-09-17")
    assert s.horizon_years == 2


def test_tp08_cycle_order_preserved():
    region, cat = make_region(), make_catalogs()
    s = _rotation(cat)
    for ch in enumerate_cohorts(s, region, cat, np.datetime64("2021-01-01"), np.datetime64("2025-12-31")):
        cyc = ch.cycles
        for k in range(len(cyc)):
            assert cyc[k].plant_date < cyc[k].harvest_date
        for k in range(len(cyc) - 1):
            fallow = s.cycles[k].fallow_after_days
            assert cyc[k].harvest_date <= cyc[k + 1].plant_date - np.timedelta64(fallow, "D")


def test_cohorts_limited_by_data_window():
    region, cat = make_region(), make_catalogs()
    one = enumerate_cohorts(simple_strategy(), region, cat, np.datetime64("2021-01-01"), np.datetime64("2025-12-31"))
    two = enumerate_cohorts(_rotation(cat), region, cat, np.datetime64("2021-01-01"), np.datetime64("2025-12-31"))
    assert len({c.cohort_year for c in one}) == 5
    assert len({c.cohort_year for c in two}) == 4


def test_validators():
    region, cat = make_region(), make_catalogs()
    bad = Strategy("B", "b", (StrategyCycle(1, "primera", (Component("maiz_t"),), WindowMode.CANDIDATE_DATES),
                              StrategyCycle(2, "postrera", (Component("frijol_t"),), WindowMode.CANDIDATE_DATES)))
    with pytest.raises(MultipleSweepCycles):
        validate_strategy(bad, cat, region)
    frac = Strategy("F", "f", (StrategyCycle(1, "primera", (Component("maiz_t", area_fraction=0.6),
                                                            Component("frijol_t", "acompanante", 0.3)), WindowMode.CANDIDATE_DATES),))
    with pytest.raises(StrategyValidationError):
        validate_strategy(frac, cat, region)


def test_association_each_component_evaluated_separately():
    region, cat = make_region(), make_catalogs()
    milpa = Strategy("M", "m", (StrategyCycle(1, "primera", (Component("maiz_t", "principal", 0.6),
                                                             Component("frijol_t", "acompanante", 0.4, 15)),
                                              WindowMode.CANDIDATE_DATES),))
    res = _results(region, cat, milpa)
    r = res[0]
    assert len(r.components) == 2
    crit = [c.state["central"] is CellState.CRITICAL for c in r.components]
    assert (r.state is CellState.CRITICAL) == any(crit)


def test_short_partial_segments_not_compared_with_threshold():
    region = make_region(min_segment_days=5)
    s = synthetic_series()
    cat = make_catalogs()
    clim = curated(s, region)
    for ch in enumerate_cohorts(simple_strategy(), region, cat, s.dates[0], s.dates[-1])[:20]:
        r = evaluate_cycle_exposure(ch.cycles[0], clim, cat, region)
        for g in r.components[0].segments:
            if g.n_days < 5:
                assert g.over["central"] is None
