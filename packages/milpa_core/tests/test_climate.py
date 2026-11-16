"""T-U y T-G de clima: ET0 FAO-56 y presión de vapor; Pef (T-P02, T-P04)."""
import numpy as np
import pytest

from milpa_core.climate.dekad import dekad_length, dekad_of
from milpa_core.climate.et0 import (actual_vp, clear_sky_radiation, es_from, et0_fao56, extraterrestrial_radiation,
                                    net_longwave, pressure_kpa, psychro, sat_vp, slope_vp, wind_to_2m)
from milpa_core.climate.peff import fao_dependable_month, pef_daily, pef_monthly, usda_scs_fao_month
from milpa_core.enums import EaMethod, PeffMethod

TOL_ET0 = 0.1  # mm/d — tolerancia de trabajo; el ADR de pruebas la fija [Verificar]


# ---------------------------------------------------------------- T-G01/T-G02 FAO-56

def test_tg02_ra_fao56_example8():
    # FAO-56 ej. 8: 20°S, 3 de septiembre (J=246) → Ra = 32.2 MJ m-2 d-1
    assert extraterrestrial_radiation(-20.0, 246) == pytest.approx(32.2, abs=0.1)


def test_tg01_et0_fao56_example18_brussels():
    # FAO-56 ej. 18: Bruselas, 6 de julio, 50°48'N, z=100 m → ET0 ≈ 3.9 mm/d
    lat, z, j = 50.80, 100.0, 187
    tmax, tmin = 21.5, 12.3
    ea = 1.409
    u2 = wind_to_2m(10 / 3.6, 10.0)
    assert u2 == pytest.approx(2.078, abs=0.01)
    ra = extraterrestrial_radiation(lat, j)
    assert ra == pytest.approx(41.09, abs=0.1)
    rs = 22.07
    rso = clear_sky_radiation(ra, z)
    assert rso == pytest.approx(30.90, abs=0.1)
    assert net_longwave(tmax, tmin, ea, rs, rso) == pytest.approx(3.71, abs=0.05)
    et0, neg = et0_fao56(np.array([tmax]), np.array([tmin]), np.array([rs]), np.array([u2]), np.array([ea]), z, lat, j)
    assert et0[0] == pytest.approx(3.9, abs=TOL_ET0)
    assert not neg[0]


def test_terms_fao56():
    assert sat_vp(25.0) == pytest.approx(3.168, abs=1e-3)  # tabla 2.3
    assert slope_vp(25.0) == pytest.approx(0.189, abs=1e-3)
    assert pressure_kpa(1800) == pytest.approx(81.8, abs=0.1)  # ej. 2
    assert psychro(1800) == pytest.approx(0.054, abs=1e-3)


# ---------------------------------------------------------------- casos límite

def test_ea_routes_and_cap():
    tmax = np.array([30.0, 30.0, 30.0, 25.0])
    tmin = np.array([20.0, 20.0, 20.0, 25.0])  # último: Tmax = Tmin
    tdew = np.array([18.0, np.nan, 35.0, 24.0])  # NaN → ruta RH; 35 > Tmax → falla QC → ruta RH
    rh = np.array([60.0, 60.0, 120.0, 99.0])  # 120 inválido → sin ea
    ea, m, capped = actual_vp(tmax, tmin, tdew, rh)
    assert m[0] == EaMethod.DEWPOINT.value and ea[0] == pytest.approx(sat_vp(18.0))
    assert m[1] == EaMethod.RH_MEAN.value and ea[1] == pytest.approx(0.6 * es_from(30, 20))
    assert m[2] == EaMethod.MISSING.value and np.isnan(ea[2])
    assert m[3] == EaMethod.DEWPOINT.value
    assert np.all(ea[np.isfinite(ea)] <= es_from(tmax, tmin)[np.isfinite(ea)] + 1e-12)


def test_ea_greater_than_es_is_capped():
    ea, m, capped = actual_vp(np.array([20.0]), np.array([10.0]), None, None)
    assert np.isnan(ea[0])
    ea, m, capped = actual_vp(np.array([20.0]), np.array([20.0]), np.array([20.4]), None)
    assert capped[0] and ea[0] == pytest.approx(es_from(20.0, 20.0))


def test_et0_negative_clipped_and_flagged():
    et0, neg = et0_fao56(np.array([5.0]), np.array([4.0]), np.array([0.5]), np.array([0.5]), np.array([0.9]), 0.0, 60.0, 355)
    assert et0[0] >= 0.0


@pytest.mark.parametrize("z", [0.0, 3000.0])
def test_et0_elevation_extremes_finite(z):
    et0, _ = et0_fao56(np.array([30.0]), np.array([18.0]), np.array([20.0]), np.array([2.0]), np.array([1.5]), z, 14.8, 150)
    assert np.isfinite(et0[0]) and et0[0] > 0


def test_leap_year_dekads():
    d = np.arange(np.datetime64("2024-02-01"), np.datetime64("2024-03-01"))
    y, idx, key = dekad_of(d)
    assert set(idx) == {4, 5, 6}
    assert dekad_length(2024, 6) == 9 and dekad_length(2023, 6) == 8 and dekad_length(2023, 3) == 11


# ---------------------------------------------------------------- Pef (T-P02, T-P04)

@pytest.mark.parametrize("f", [usda_scs_fao_month, fao_dependable_month])
def test_tp02_monthly_peff_bounds_and_monotone(f):
    p = np.linspace(0, 600, 601)
    e = f(p)
    assert np.all(e >= -1e-12) and np.all(e <= p + 1e-9)
    assert np.all(np.diff(e) >= -1e-9)
    assert f(np.array([0.0]))[0] == 0.0


@pytest.mark.parametrize("method", [PeffMethod.USDA_SCS_FAO, PeffMethod.FAO_DEPENDABLE])
def test_tp02_dekads_sum_to_month(method):
    rng = np.random.default_rng(0)
    for _ in range(50):
        d = np.arange(np.datetime64("2023-01-01"), np.datetime64("2024-01-01"))
        p = np.where(rng.uniform(size=d.size) < 0.4, rng.gamma(0.9, 15, d.size), 0.0)
        daily = pef_daily(d, p, method)
        keys, pm, em = pef_monthly(d, p, method)
        f = usda_scs_fao_month if method is PeffMethod.USDA_SCS_FAO else fao_dependable_month
        assert np.allclose(em, f(pm), atol=1e-9)
        y, idx, dk = dekad_of(d)
        for k in np.unique(dk):
            assert np.sum(daily[dk == k]) <= np.sum(p[dk == k]) + 1e-9


def test_tp04_missing_rain_is_never_zero():
    rng = np.random.default_rng(3)
    for _ in range(30):
        d = np.arange(np.datetime64("2022-01-01"), np.datetime64("2023-01-01"))
        p = rng.gamma(0.9, 10, d.size)
        miss = rng.choice(d.size, size=rng.integers(1, 10), replace=False)
        p[miss] = np.nan
        out = pef_daily(d, p, PeffMethod.USDA_SCS_FAO)
        mk = d.astype("datetime64[M]")
        bad_months = np.unique(mk[miss])
        for m in bad_months:
            assert np.all(np.isnan(out[mk == m]))
        good = ~np.isin(mk, bad_months)
        assert np.all(np.isfinite(out[good]))


def test_incomplete_month_is_nan():
    d = np.arange(np.datetime64("2022-01-15"), np.datetime64("2022-03-01"))
    out = pef_daily(d, np.ones(d.size), PeffMethod.USDA_SCS_FAO)
    assert np.all(np.isnan(out[d < np.datetime64("2022-02-01")]))
    assert np.all(np.isfinite(out[d >= np.datetime64("2022-02-01")]))


def test_fixed_fraction_requires_phi():
    d = np.arange(np.datetime64("2022-01-01"), np.datetime64("2022-02-01"))
    with pytest.raises(ValueError):
        pef_daily(d, np.ones(d.size), PeffMethod.FIXED_FRACTION)
    assert np.allclose(pef_daily(d, np.ones(d.size), PeffMethod.FIXED_FRACTION, 0.7), 0.7)
