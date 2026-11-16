"""Fachada pública estable (apartado 10): run_analysis, rank, rank_stability, soil_voi, build_report.

Orquestación de una corrida (apartado 11.13). Sin E/S: todo entra por ``RunContext``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Mapping, Any

import numpy as np

from .climate.series import ClimateSeries, CuratedClimate, derive_climate
from .config import RankingConfig, RegionConfig, RiskConfig, SoilCriterionConfig, StabilityConfig, VoiConfig
from .criteria import build_criteria, eligibility
from .crops import Catalogs
from .enums import AdaptationMode, Criterion, Mode, RankingStatus, Reason
from .exposure import CycleResult, evaluate_cycle_exposure
from .gating import GatingConfig, ModeDecision, decide_mode
from .provenance import ScenarioTag
from .ranking import RankingResult, StabilityResult, rank as _rank, rank_stability as _rank_stability
from .risk import CycleRisk, StrategyRisk, aggregate_cycle, aggregate_strategy, assign_consistency
from .rootzone import evaluate_cycle_rootzone
from .scenarios import BASE, ScenarioDef, apply_scenario, make_onset_fn
from .soil import SoilContext
from .soil.voi import VoiResult, soil_voi as _soil_voi
from .strategy import Strategy, enumerate_cohorts, validate_strategy

ENGINE_VERSION = "milpa_core 0.1.0"


@dataclass(frozen=True)
class RunContext:
    region: RegionConfig
    catalogs: Catalogs
    climate: ClimateSeries
    base_climate: CuratedClimate
    strategies: tuple[Strategy, ...]
    soil: SoilContext = field(default_factory=SoilContext)
    crops_enabled: tuple[str, ...] | None = None
    risk_cfg: RiskConfig = field(default_factory=RiskConfig)
    ranking_cfg: RankingConfig = field(default_factory=RankingConfig)
    stability_cfg: StabilityConfig = field(default_factory=StabilityConfig)
    voi_cfg: VoiConfig = field(default_factory=VoiConfig)
    gating_cfg: GatingConfig = field(default_factory=GatingConfig)
    soil_cfg: SoilCriterionConfig = field(default_factory=SoilCriterionConfig)
    seed: int = 0
    run_id: str = "local"
    data_hash: str = ""
    region_config_hash: str = ""
    warnings: tuple[str, ...] = ()


def make_context(region: RegionConfig, catalogs: Catalogs, climate: ClimateSeries, strategies: list[Strategy],
                 soil: SoilContext | None = None, **kw) -> RunContext:
    warns: list[str] = []
    for s in strategies:
        warns += validate_strategy(s, catalogs, region)
    base = derive_climate(climate, region.lat_deg, region.elevation_m, region.peff_enabled, region.phi,
                          region.ea_sensitivity_tol_pct)
    risk_cfg = kw.pop("risk_cfg", RiskConfig(min_valid_years=region.min_valid_years))
    h = hashlib.sha256()
    for a in (climate.precip_mm, climate.tmax_c, climate.tmin_c, climate.srad_mj_m2, climate.wind2m_ms):
        h.update(np.nan_to_num(np.asarray(a, dtype=float), nan=-9999.0).tobytes())
    rh = hashlib.sha256(json.dumps(region.__dict__, default=str, sort_keys=True).encode()).hexdigest()
    return RunContext(region, catalogs, climate, base, tuple(strategies), soil or SoilContext(), risk_cfg=risk_cfg,
                      data_hash=h.hexdigest(), region_config_hash=rh, warnings=tuple(warns), **kw)


@dataclass(frozen=True)
class ScenarioRunResult:
    scenario: ScenarioDef
    tag: ScenarioTag
    adaptation: AdaptationMode
    decision: ModeDecision
    cycle_results: tuple[CycleResult, ...]
    cycle_risk: tuple[CycleRisk, ...]
    strategy_risk: tuple[StrategyRisk, ...]
    climate: CuratedClimate
    limitations: tuple[str, ...] = ()
    meta: Mapping[str, object] = field(default_factory=dict)


def _tmean_fn(clim: CuratedClimate):
    tm = clim.tmean_c()

    def fn(day: np.datetime64):
        i = clim.base.index_of(day)
        if i < 0 or i >= tm.size:
            return None
        return tm[i:]

    return fn


def run_analysis(ctx: RunContext, scenario: ScenarioDef = BASE, adaptation: AdaptationMode = AdaptationMode.NONE,
                 step_days: int | None = None) -> ScenarioRunResult:
    decision = decide_mode(ctx.soil, list(ctx.strategies), ctx.catalogs, ctx.gating_cfg)
    clim = apply_scenario(ctx.climate, ctx.base_climate, scenario, ctx.region)
    if adaptation is AdaptationMode.ONSET_RULE and not ctx.region.onset_rule_enabled:
        raise ValueError("onset_rule deshabilitada: falta definición de inicio de lluvias o lag con cita")
    onset_fn = make_onset_fn(clim, ctx.region) if adaptation is AdaptationMode.ONSET_RULE else None
    tmean_fn = _tmean_fn(clim)
    results: list[CycleResult] = []
    for strat in ctx.strategies:
        cohorts = enumerate_cohorts(strat, ctx.region, ctx.catalogs, clim.dates[0], clim.dates[-1], tmean_fn, onset_fn,
                                    adaptation, step_days)
        for ch in cohorts:
            for ci in ch.cycles:
                if scenario.onset_delay_days and clim.onset_day_idx.get(ci.agri_year, 0) == -1:
                    ci = replace(ci, invalid_reason="sin_inicio_de_lluvias_detectable")
                if decision.mode is Mode.EXPOSURE:
                    results.append(evaluate_cycle_exposure(ci, clim, ctx.catalogs, ctx.region))
                else:
                    results.append(evaluate_cycle_rootzone(ci, clim, ctx.catalogs, ctx.region, ctx.soil))
    tol = ctx.region.communication_tol_pct
    crisk = aggregate_cycle(results, ctx.risk_cfg, tol)
    horizons = {s.code: s.horizon_years for s in ctx.strategies}
    srisk = assign_consistency(aggregate_strategy(results, ctx.risk_cfg, horizons, crisk, tol))
    lim = []
    if scenario.delta_t_c and any(ctx.catalogs.varieties[v].phenology_basis == "days" for s in ctx.strategies for v in s.varieties()):
        lim.append(Reason.FENOLOGIA_FIJA_EN_DIAS.value)
    if decision.mode is Mode.EXPOSURE:
        lim.append("indicador de exposición climática: no es déficit real de agua del suelo")
    if ctx.region.status == "sandbox":
        lim.append("modo sandbox: catálogos y umbrales provisionales — no usar para decisión")
    meta = {"engine_version": ENGINE_VERSION, "run_id": ctx.run_id, "data_hash": ctx.data_hash,
            "region_config_hash": ctx.region_config_hash, "catalog_hash": ctx.catalogs.catalog_hash, "seed": ctx.seed,
            "mass_dropped_mm": clim.mass_dropped_mm, "peff_primary": ctx.region.primary_peff.value,
            "ea_route_diff_pct": clim.ea_route_diff_pct, "climate_flags": list(clim.flags),
            "period": [str(clim.dates[0]), str(clim.dates[-1])]}
    return ScenarioRunResult(scenario, scenario.tag(adaptation), adaptation, decision, tuple(results), tuple(crisk),
                             tuple(srisk), clim, tuple(lim), meta)


# ------------------------------------------------------------------ ranking

def select_anchor(risks: tuple[StrategyRisk, ...], strategy: Strategy, policy: str, anchor_md: Mapping[str, str] | None = None
                  ) -> StrategyRisk | None:
    """Qué fecha ancla representa a una estrategia que barre fechas en el ranking.

    policy='window_start' (defecto, sin sesgo de selección) | 'explicit' (anchor_md por estrategia).
    """
    rs = [r for r in risks if r.strategy == strategy.code]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    if policy == "explicit" and anchor_md and strategy.code in anchor_md:
        for r in rs:
            if r.anchor_md == anchor_md[strategy.code]:
                return r
    return sorted(rs, key=lambda r: r.anchor_md or "")[0]


def build_strategy_criteria(ctx: RunContext, run: ScenarioRunResult, anchor_policy: str = "window_start",
                            anchor_md: Mapping[str, str] | None = None, ph_override: float | None = None):
    chosen = {s.code: select_anchor(run.strategy_risk, s, anchor_policy, anchor_md) for s in ctx.strategies}
    crit = build_criteria(list(ctx.strategies), {k: v for k, v in chosen.items() if v is not None}, ctx.catalogs, ctx.soil,
                          ctx.soil_cfg, ph_override)
    elig = {}
    for s in ctx.strategies:
        e = eligibility(s, ctx.catalogs, ctx.soil, ctx.crops_enabled, ph_override)
        elig[s.code] = (e.eligible, e.reasons)
    return crit, elig, chosen


def rank(ctx: RunContext, run: ScenarioRunResult, weights: Mapping[Criterion, float] | None = None,
         cfg: RankingConfig | None = None, anchor_policy: str = "window_start", anchor_md: Mapping[str, str] | None = None,
         ph_override: float | None = None) -> tuple[RankingResult, dict[str, Any]]:
    w = dict(weights or ctx.region.priorities_default)
    crit, elig, chosen = build_strategy_criteria(ctx, run, anchor_policy, anchor_md, ph_override)
    byc = {k: v.by_year_crit for k, v in chosen.items() if v is not None}
    res = _rank(crit, w, cfg or ctx.ranking_cfg, elig, byc)
    log = list(res.decision_log) + [{"decision": "fecha_ancla_para_ranking", "policy": anchor_policy,
                                     "anchors": {k: (v.anchor_md if v else None) for k, v in chosen.items()}}]
    res = replace(res, decision_log=tuple(log))
    return res, {"criteria": crit, "eligibility": elig, "anchors": {k: (v.anchor_md if v else None) for k, v in chosen.items()}}


def rank_stability(base: RankingResult, cfg: StabilityConfig) -> StabilityResult:
    return _rank_stability(base, cfg)


def soil_voi(ctx: RunContext, run: ScenarioRunResult, base: RankingResult, weights: Mapping[Criterion, float] | None = None,
             cfg: VoiConfig | None = None) -> VoiResult:
    cfg = cfg or ctx.voi_cfg
    crops = {s.code: {ctx.catalogs.varieties[v].crop for v in s.varieties()} for s in ctx.strategies}

    def rerank(ph: float):
        r, extra = rank(ctx, run, weights, ph_override=ph)
        excluded = tuple(k for k, (ok, _why) in extra["eligibility"].items() if not ok)
        return r.order, excluded

    return _soil_voi(ctx.soil, base.order, base.status, crops, ctx.catalogs, rerank, cfg)


def run_grid(ctx: RunContext, scenarios: list[ScenarioDef], adaptations=(AdaptationMode.NONE,), step_days: int | None = None):
    """Ejecuta la grilla; los escenarios no aplicables se devuelven con su motivo (no se inventan)."""
    from .errors import ScenarioNotApplicable

    out, skipped = {}, {}
    for sc in scenarios:
        for ad in adaptations:
            try:
                out[(sc.scenario_id, ad.value)] = run_analysis(ctx, sc, ad, step_days)
            except (ScenarioNotApplicable, ValueError) as e:
                skipped[(sc.scenario_id, ad.value)] = str(e)
    return out, skipped


def compare_to_base(base_rank: RankingResult, sc_rank: RankingResult, base_run: ScenarioRunResult, sc_run: ScenarioRunResult) -> dict[str, Any]:
    inv = 0
    if base_rank.status is RankingStatus.OK and sc_rank.status is RankingStatus.OK:
        pos = {s: i for i, s in enumerate(sc_rank.order)}
        o = base_rank.order
        inv = sum(1 for i in range(len(o)) for j in range(i + 1, len(o)) if pos.get(o[i], 0) > pos.get(o[j], 0))
    dsev = {}
    b = {(r.strategy, r.anchor_md): r for r in base_run.strategy_risk}
    for r in sc_run.strategy_risk:
        rb = b.get((r.strategy, r.anchor_md))
        if rb and rb.p90_severity_by_agri_year_mm is not None and r.p90_severity_by_agri_year_mm is not None:
            dsev[f"{r.strategy}@{r.anchor_md}"] = r.p90_severity_by_agri_year_mm - rb.p90_severity_by_agri_year_mm
    return {"scenario_id": sc_run.scenario.scenario_id, "rank_inversions_vs_base": inv, "delta_p90_severity_mm": dsev,
            "top_base": base_rank.order[0] if base_rank.order else None,
            "top_scenario": sc_rank.order[0] if sc_rank.order else None}


def humidity_sensitivity_flags(results: Mapping[tuple, ScenarioRunResult], tol_pct: float) -> dict[str, bool]:
    """escenario_sensible_a_humedad: compara Hrh vs Hea en frecuencia agrupada."""
    flags = {}
    for (sid, ad), r in results.items():
        if not sid.endswith("_Hrh"):
            continue
        alt = results.get((sid[:-3] + "Hea", ad))
        if alt is None:
            continue
        a = {(x.strategy, x.anchor_md): x.pooled_critical_share_pct for x in r.strategy_risk}
        b = {(x.strategy, x.anchor_md): x.pooled_critical_share_pct for x in alt.strategy_risk}
        diff = max((abs(a[k] - b[k]) for k in a if a.get(k) is not None and b.get(k) is not None), default=0.0)
        flags[sid] = diff > tol_pct
    return flags
