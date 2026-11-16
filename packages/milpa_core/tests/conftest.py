"""Fixtures compartidas: región, catálogo y estrategias mínimas construidas en código (sin E/S)."""
from __future__ import annotations

import numpy as np
import pytest

from milpa_core.climate.series import ClimateSeries, derive_climate
from milpa_core.config import RegionConfig, Season
from milpa_core.crops import Catalogs, Crop, Stage, Threshold, Variety
from milpa_core.enums import PeffMethod, ThresholdMetric, WindowMode
from milpa_core.strategy import Component, Strategy, StrategyCycle

EPS = 1e-9


def make_region(**kw) -> RegionConfig:
    base = dict(code="test", status="sandbox", lat_deg=14.8, elevation_m=450.0, window_start="2021-01-01",
                window_end="2025-12-31",
                seasons={"primera": Season("primera", 0, ("05-01", "06-15")), "postrera": Season("postrera", 0, ("08-20", "09-30"))},
                min_valid_years=3, step_days=5)
    base.update(kw)
    return RegionConfig(**base)


def maize(code="maiz_t", lengths=(20, 35, 40, 30), cited=False) -> Variety:
    cit = "FAO-56" if cited else None
    st = (Stage("INI", 1, 0.3, 0.3, False, lengths[0], citation=cit), Stage("DEV", 2, 0.3, 1.2, False, lengths[1], citation=cit),
          Stage("MID", 3, 1.2, 1.2, True, lengths[2], citation=cit), Stage("LATE", 4, 1.2, 0.35, False, lengths[3], citation=cit))
    return Variety(code, "maiz", code, "days", st, "Poaceae", z_min_m=0.15, z_max_m=1.0, depletion_fraction_p=0.55)


def bean(code="frijol_t") -> Variety:
    st = (Stage("INI", 1, 0.4, 0.4, False, 15), Stage("DEV", 2, 0.4, 1.15, False, 25),
          Stage("MID", 3, 1.15, 1.15, True, 35), Stage("LATE", 4, 1.15, 0.35, False, 20))
    return Variety(code, "frijol", code, "days", st, "Fabaceae", z_min_m=0.15, z_max_m=0.6, depletion_fraction_p=0.45)


def make_catalogs(thr=60.0, low=50.0, high=68.0, cited=False, **kw) -> Catalogs:
    crops = {"maiz": Crop("maiz", "Maíz", "Poaceae"), "frijol": Crop("frijol", "Frijol", "Fabaceae", True)}
    vs = {v.code: v for v in (maize(cited=cited), maize("maiz_largo", (25, 40, 45, 30), cited), bean())}
    c = "cita" if cited else None
    th = (Threshold("maiz", "MID", ThresholdMetric.DEKAD_EXPOSURE_MM, thr, low, high, citation=c),
          Threshold("frijol", "MID", ThresholdMetric.DEKAD_EXPOSURE_MM, thr, low, high, citation=c))
    return Catalogs(crops, vs, th, **kw)


def simple_strategy(code="S1", variety="maiz_t", mode=WindowMode.CANDIDATE_DATES, window=None) -> Strategy:
    return Strategy(code, code, (StrategyCycle(1, "primera", (Component(variety),), mode, plant_window=window),))


def synthetic_series(seed=1, start="2021-01-01", end="2025-12-31", rain_scale=1.0) -> ClimateSeries:
    rng = np.random.default_rng(seed)
    d = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"))
    doy = (d - d.astype("datetime64[Y]")).astype(int) + 1
    wet = 0.55 * np.exp(-0.5 * ((doy - 160) / 18) ** 2) + 0.6 * np.exp(-0.5 * ((doy - 265) / 22) ** 2) + 0.03
    p = np.where(rng.uniform(size=d.size) < wet, rng.gamma(0.9, 12.0, d.size), 0.0) * rain_scale
    tmax = 31 + 3 * np.sin(2 * np.pi * (doy - 100) / 365) - 2.5 * wet
    tmin = 18 + 2 * np.sin(2 * np.pi * (doy - 120) / 365) + 1.5 * wet
    return ClimateSeries(d, tmax, tmin, p, np.full(d.size, 2.0), 22 - 7 * wet, tdew_c=tmin - 1.0,
                         rh_pct=np.clip(55 + 35 * wet, 15, 99))


PEFF = (PeffMethod.USDA_SCS_FAO, PeffMethod.FAO_DEPENDABLE, PeffMethod.UPPER_BOUND)


def curated(series=None, region=None):
    region = region or make_region()
    series = series or synthetic_series()
    return derive_climate(series, region.lat_deg, region.elevation_m, PEFF)


@pytest.fixture
def region():
    return make_region()


@pytest.fixture
def catalogs():
    return make_catalogs()


@pytest.fixture
def series():
    return synthetic_series()
