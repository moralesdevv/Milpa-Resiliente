"""Modelo temporal de estrategias, rotaciones y cohortes (apartado 11.6)."""
from __future__ import annotations

from typing import Any

from dataclasses import dataclass

import numpy as np

from ..config import RegionConfig
from ..crops import Calendar, Catalogs, Variety, build_calendar
from ..enums import AdaptationMode, StrategyAxis, WindowMode
from ..errors import MultipleSweepCycles, StrategyValidationError


def D(n: int) -> np.timedelta64:
    return np.timedelta64(int(n), "D")


@dataclass(frozen=True)
class Component:
    variety: str
    role: str = "principal"  # principal | acompanante | cobertura
    area_fraction: float = 1.0
    plant_offset_days: int = 0


@dataclass(frozen=True)
class StrategyCycle:
    cycle_idx: int
    season: str
    components: tuple[Component, ...]
    window_mode: WindowMode
    agri_year_offset: int = 0
    plant_window: tuple[str, str] | None = None  # MM-DD; si None usa la de la temporada
    rel_lag_days: int = 0
    fallow_after_days: int = 0
    soil_carryover: bool = False


@dataclass(frozen=True)
class Strategy:
    code: str
    name: str
    cycles: tuple[StrategyCycle, ...]
    version: int = 1
    changes_from_reference: tuple[StrategyAxis, ...] = ()
    is_reference: bool = False
    anchor_cycle_idx: int = 1
    enabled_by_farmer: bool = True
    farmer_constraint_reason: str | None = None

    @property
    def horizon_years(self) -> int:
        return max(c.agri_year_offset for c in self.cycles) + 1

    @property
    def kind(self) -> str:
        ax = set(self.changes_from_reference)
        if not ax:
            return "reference" if self.is_reference else "simple"
        if len(ax) > 1:
            return "compuesta"
        return next(iter(ax)).value

    def varieties(self) -> list[str]:
        return [comp.variety for c in self.cycles for comp in c.components]

    def sweep_cycle(self) -> StrategyCycle | None:
        sw = [c for c in self.cycles if c.window_mode is WindowMode.CANDIDATE_DATES]
        return sw[0] if sw else None


def validate_strategy(s: Strategy, catalogs: Catalogs, region: RegionConfig) -> list[str]:
    """Invariantes del cargador. Lanza en errores duros; devuelve advertencias."""
    warnings: list[str] = []
    idx = [c.cycle_idx for c in s.cycles]
    if idx != list(range(1, len(idx) + 1)):
        raise StrategyValidationError(f"{s.code}: cycle_idx debe ser 1..n estricto")
    sweeps = [c for c in s.cycles if c.window_mode is WindowMode.CANDIDATE_DATES]
    if len(sweeps) > 1:
        raise MultipleSweepCycles(f"{s.code}: solo un ciclo puede barrer fechas candidatas")
    if sweeps and sweeps[0].cycle_idx != s.anchor_cycle_idx:
        raise StrategyValidationError(f"{s.code}: el ciclo que barre fechas debe ser el ancla")
    if s.cycles[0].window_mode is WindowMode.RELATIVE_TO_PREVIOUS_HARVEST:
        raise StrategyValidationError(f"{s.code}: el primer ciclo no puede ser relativo a una cosecha anterior")
    offs = [c.agri_year_offset for c in s.cycles]
    if offs != sorted(offs):
        raise StrategyValidationError(f"{s.code}: agri_year_offset no puede decrecer")
    for c in s.cycles:
        if c.season not in region.seasons:
            raise StrategyValidationError(f"{s.code}: temporada {c.season} no está en el region pack")
        tot = sum(comp.area_fraction for comp in c.components)
        if abs(tot - 1.0) > 1e-6:
            raise StrategyValidationError(f"{s.code} ciclo {c.cycle_idx}: suma de area_fraction = {tot:.3f} ≠ 1")
        for comp in c.components:
            if comp.variety not in catalogs.varieties:
                raise StrategyValidationError(f"{s.code}: variedad {comp.variety} no está en el catálogo")
    if StrategyAxis.PLANTING_DATE in s.changes_from_reference and StrategyAxis.ROTATION in s.changes_from_reference \
            and len(s.changes_from_reference) == 1:
        warnings.append("una modificación de fecha nunca se etiqueta como rotación")
    return warnings


# ------------------------------------------------------------------ instancias

def md_date(year: int, md: str) -> np.datetime64:
    return np.datetime64(f"{year:04d}-{md}", "D")


def candidate_dates(year: int, window: tuple[str, str], step_days: int) -> list[np.datetime64]:
    a, b = md_date(year, window[0]), md_date(year, window[1])
    if b < a:
        raise StrategyValidationError("ventana de siembra invertida")
    n = int((b - a).astype(int)) // step_days + 1
    return [a + D(i * step_days) for i in range(n)]


@dataclass(frozen=True)
class ComponentInstance:
    component: Component
    variety: Variety
    plant_date: np.datetime64
    calendar: Calendar | None


@dataclass(frozen=True)
class CycleInstance:
    strategy: str
    cohort_year: int
    cycle_idx: int
    anchor_md: str | None
    season: str
    agri_year: int
    plant_date: np.datetime64 | None
    harvest_date: np.datetime64 | None
    components: tuple[ComponentInstance, ...]
    calendar_year: int
    invalid_reason: str | None = None
    adapted: bool = False

    @property
    def principal_variety(self) -> str:
        for c in self.components:
            if c.component.role == "principal":
                return c.variety.code
        return self.components[0].variety.code if self.components else ""


@dataclass(frozen=True)
class CohortInstance:
    strategy: Strategy
    cohort_year: int
    anchor_md: str | None
    cycles: tuple[CycleInstance, ...]
    in_window: bool

    @property
    def key(self) -> tuple[Any, ...]:
        return (self.strategy.code, self.cohort_year, self.anchor_md)


def _season_window(c: StrategyCycle, region: RegionConfig) -> tuple[str, str]:
    return c.plant_window or region.seasons[c.season].plant_window


def _build_components(c: StrategyCycle, plant: np.datetime64, catalogs: Catalogs, tmean_fn) -> tuple[tuple[ComponentInstance, ...], np.datetime64 | None]:
    comps = []
    harvest = None
    for comp in c.components:
        v = catalogs.varieties[comp.variety]
        pd = plant + D(comp.plant_offset_days)
        tm = tmean_fn(pd) if v.phenology_basis == "gdd" else None
        cal = build_calendar(v, pd, tm) if (v.phenology_basis == "days" or tm is not None) else None
        comps.append(ComponentInstance(comp, v, pd, cal))
        if cal is None:
            harvest = None
            return tuple(comps), None
        harvest = cal.harvest_date if harvest is None else max(harvest, cal.harvest_date)
    return tuple(comps), harvest


def instantiate_cohort(
    s: Strategy,
    cohort_year: int,
    anchor_date: np.datetime64 | None,
    region: RegionConfig,
    catalogs: Catalogs,
    data_start: np.datetime64,
    data_end: np.datetime64,
    tmean_fn=None,
    onset_fn=None,
    adaptation: AdaptationMode = AdaptationMode.NONE,
    candidate_step: int | None = None,
) -> CohortInstance:
    """Instancia todos los ciclos de la cohorte con año de inicio ``cohort_year``.

    Reglas de fechas (declaradas en METHODS.md):
      candidate_dates               → fecha ancla (o, con onset_rule, primera candidata ≥ t0' + lag)
      fixed_season_window           → inicio de la ventana de la temporada en su año calendario
      relative_to_previous_harvest  → cosecha_{k-1} + 1 + fallow_{k-1} + rel_lag_days
    """
    cycles: list[CycleInstance] = []
    prev_harvest: np.datetime64 | None = None
    prev_fallow = 0
    in_window = True
    anchor_md = None if anchor_date is None else str(anchor_date)[5:]
    for c in s.cycles:
        season = region.seasons[c.season]
        agri_year = cohort_year + c.agri_year_offset
        cal_year = agri_year + season.calendar_year_shift
        reason = None
        adapted = False
        if c.window_mode is WindowMode.CANDIDATE_DATES:
            plant = md_date(cal_year, anchor_md) if anchor_md else md_date(cal_year, _season_window(c, region)[0])
            if adaptation is AdaptationMode.ONSET_RULE and onset_fn is not None:
                t0 = onset_fn(agri_year)
                if t0 is None:
                    plant, reason = None, "sin_inicio_de_lluvias_detectable"
                else:
                    cands = candidate_dates(cal_year, _season_window(c, region), candidate_step or region.step_days)
                    target = t0 + D(int(region.adaptation_lag_days or 0))
                    later = [d for d in cands if d >= target]
                    plant = later[0] if later else None
                    reason = None if later else "onset_fuera_de_ventana"
                    adapted = True
        elif c.window_mode is WindowMode.FIXED_SEASON_WINDOW:
            plant = md_date(cal_year, _season_window(c, region)[0])
        else:
            plant = None if prev_harvest is None else prev_harvest + D(1 + prev_fallow + int(c.rel_lag_days))
            if prev_harvest is None:
                reason = "cosecha_anterior_desconocida"
        harvest = None
        comps: tuple[ComponentInstance, ...] = ()
        if plant is not None:
            if prev_harvest is not None and plant < prev_harvest + D(1 + prev_fallow):
                reason = "solape_de_ciclos"
            if plant < data_start:
                in_window = False
            comps, harvest = _build_components(c, plant, catalogs, tmean_fn or (lambda d: None))
            if harvest is None and reason is None:
                reason = "calendario_no_calculable"
            if harvest is not None and harvest > data_end:
                in_window = False
        cycles.append(CycleInstance(s.code, cohort_year, c.cycle_idx, anchor_md, c.season, agri_year, plant, harvest,
                                    comps, cal_year, reason, adapted))
        prev_harvest = harvest
        prev_fallow = c.fallow_after_days
    return CohortInstance(s, cohort_year, anchor_md, tuple(cycles), in_window)


def enumerate_cohorts(
    s: Strategy,
    region: RegionConfig,
    catalogs: Catalogs,
    data_start: np.datetime64,
    data_end: np.datetime64,
    tmean_fn=None,
    onset_fn=None,
    adaptation: AdaptationMode = AdaptationMode.NONE,
    step_days: int | None = None,
) -> list[CohortInstance]:
    """Todas las cohortes (año de inicio × fecha ancla) cuyas cosechas caen en la ventana."""
    out: list[CohortInstance] = []
    sw = s.sweep_cycle()
    for y in range(region.start_year, region.end_year + 1):
        if sw is not None:
            if adaptation is AdaptationMode.ONSET_RULE:
                anchors = [None]
            else:
                cal_year = y + sw.agri_year_offset + region.seasons[sw.season].calendar_year_shift
                anchors = candidate_dates(cal_year, _season_window(sw, region), step_days or region.step_days)
        else:
            anchors = [None]
        for a in anchors:
            ch = instantiate_cohort(s, y, a, region, catalogs, data_start, data_end, tmean_fn, onset_fn, adaptation, step_days)
            if ch.in_window:
                out.append(ch)
    return out


def n_independent_cohorts(n_years: int, horizon: int) -> int:
    return n_years // max(horizon, 1)
