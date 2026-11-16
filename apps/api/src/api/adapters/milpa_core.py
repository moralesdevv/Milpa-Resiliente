"""Adaptador hacia ``milpa_core`` (R2): delegación 1:1 a la fachada real, sin lógica científica.

R3 no copia ni reimplementa el motor (CLAUDE.md §2, §5). Este módulo:
  * importa ``milpa_core`` de forma perezosa;
  * verifica que la fachada pública coincida con las firmas REALES publicadas por R2
    (``DOCUMENTED_FACADE``; difieren de las del README §10, ver ``docs/r2/README_R2.md``);
  * lee entradas con ``api.adapters.core_io`` (E/S) y delega el cálculo al motor;
  * traduce los resultados a JSON con los DTO de R2 (``milpa_core.dto``), sin alterar valores.

La persistencia (``engine.analysis_run`` / ``scenario_run`` / Parquet) NO se hace aquí: la hace el
handler del trabajo con lo que este adaptador devuelve.

Lo que R2 no publica no se inventa: ``climate_history`` sigue ``PENDING_R2`` y una corrida con
parcela (``SoilContext`` desde suelo declarado/medido) tampoco está cableada.
"""

from __future__ import annotations

import importlib
import inspect
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID

from api.adapters import core_io
from api.adapters.ports import RunRef
from api.errors import DependencyNotIntegrated, NotFound, ValidationFailed

# Parámetros posicionales REALES de la fachada de ``milpa_core`` (R2). El README §10 documenta otros
# nombres (``results``, ``parcel``, ``bundle``…); se corrigió a lo publicado, no se inventó nada.
DOCUMENTED_FACADE: dict[str, tuple[str, ...]] = {
    "make_context": ("region", "catalogs", "climate", "strategies"),
    "run_analysis": ("ctx", "scenario", "adaptation", "step_days"),
    "run_grid": ("ctx", "scenarios", "adaptations", "step_days"),
    "rank": ("ctx", "run", "weights", "cfg"),
    "rank_stability": ("base", "cfg"),
    "soil_voi": ("ctx", "run", "base", "weights", "cfg"),
    "standard_grid": (),
    "build_report": ("summary", "rank", "voi", "scenarios"),
}


@dataclass(frozen=True)
class ContractReport:
    package_present: bool
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.package_present and not self.problems


def import_core() -> ModuleType | None:
    try:
        return importlib.import_module("milpa_core")
    except ModuleNotFoundError as exc:
        if exc.name == "milpa_core":
            return None
        raise


def check_core_contract(core: ModuleType | None = None) -> ContractReport:
    core = core if core is not None else import_core()
    if core is None:
        return ContractReport(False, ("paquete milpa_core no instalado (pendiente de R2)",))
    problems: list[str] = []
    for name, expected in DOCUMENTED_FACADE.items():
        fn = getattr(core, name, None)
        if not callable(fn):
            problems.append(f"falta la función pública {name}")
            continue
        params = tuple(inspect.signature(fn).parameters)[: len(expected)]
        if params != expected:
            problems.append(f"{name}: parámetros {params} != publicados {expected}")
    return ContractReport(True, tuple(problems))


@dataclass(frozen=True)
class CoreAssets:
    """Dónde están el region pack, las estrategias, los catálogos y la serie curada de cada zona."""

    region_path: Path
    strategies_path: Path
    catalogs_dir: Path
    daily_for_zone: Callable[[UUID], Path]


class MilpaCoreEngine:
    """Delegación a ``milpa_core``. Determinista: una corrida se puede reconstruir desde sus hashes."""

    component = "R2 (packages/milpa_core)"
    _CACHE_RUNS = 64

    def __init__(self, core: ModuleType, assets: CoreAssets | None = None) -> None:
        report = check_core_contract(core)
        if not report.ok:
            raise RuntimeError(
                "milpa_core no cumple la fachada publicada: " + "; ".join(report.problems)
            )
        self._core = core
        self._assets = assets
        self._ctx: OrderedDict[UUID, Any] = OrderedDict()
        self._runs: OrderedDict[tuple[UUID, str, str], Any] = OrderedDict()

    def is_available(self) -> bool:
        return self._assets is not None

    # -- infraestructura ------------------------------------------------------------------------
    def _pending(self, what: str, why: str) -> DependencyNotIntegrated:
        return DependencyNotIntegrated(self.component, f"{what} (PENDING_R2: {why})")

    def _need_assets(self) -> CoreAssets:
        if self._assets is None:
            raise DependencyNotIntegrated(
                self.component, "Rutas del region pack/catálogos/serie curada sin configurar"
            )
        return self._assets

    def _build_context(
        self, zone_id: UUID, seed: int, start: str | None, end: str | None
    ) -> tuple[Any, core_io.CuratedInfo]:
        assets = self._need_assets()
        region, extras = core_io.load_region(assets.region_path)
        catalogs = core_io.load_catalogs(assets.catalogs_dir, mode=region.status)
        strategies = core_io.load_strategies(assets.strategies_path)
        daily = assets.daily_for_zone(zone_id)
        if not daily.is_file():
            raise DependencyNotIntegrated(
                "R1 (datos curados)", f"No existe la serie curada diaria de la zona ({daily.name})"
            )
        series, info = core_io.load_curated_daily(
            daily, extras.cell_id, start or region.window_start, end or region.window_end
        )
        ctx = self._core.make_context(
            region,
            catalogs,
            series,
            strategies,
            crops_enabled=extras.crops_enabled,
            ranking_cfg=extras.ranking_cfg,
            stability_cfg=extras.stability_cfg,
            voi_cfg=extras.voi_cfg,
            soil_cfg=extras.soil_cfg,
            seed=seed,
            run_id=str(zone_id),
        )
        return ctx, info

    def _context_for(self, run: RunRef) -> Any:
        """Contexto de la corrida: de caché o reconstruido; exige que los hashes coincidan."""
        ctx = self._ctx.get(run.run_id)
        if ctx is None:
            ctx, _ = self._build_context(
                run.zone_id, run.seed, _iso(run.period_start), _iso(run.period_end)
            )
            ctx = replace(ctx, run_id=str(run.run_id))
            if ctx.data_hash != run.data_hash or ctx.region_config_hash != run.region_config_hash:
                raise ValidationFailed(
                    "Los datos o la configuración regional cambiaron desde que se creó la corrida; "
                    "no se recalcula con entradas distintas (reproducibilidad)."
                )
            self._remember(self._ctx, run.run_id, ctx)
        return ctx

    def _remember(self, cache: OrderedDict[Any, Any], key: Any, value: Any) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._CACHE_RUNS:
            cache.popitem(last=False)

    def _scenario(self, scenario_id: str) -> Any:
        for sc in [self._core.BASE, *self._core.standard_grid()]:
            if sc.scenario_id == scenario_id:
                return sc
        raise NotFound(f"Escenario '{scenario_id}' fuera de la grilla de R2")

    def _adaptation(self, value: Any) -> Any:
        from milpa_core.enums import AdaptationMode

        return AdaptationMode(str(value or "none"))

    def _result(self, run: RunRef, scenario_id: str, adaptation: Any) -> Any:
        key = (run.run_id, scenario_id, adaptation.value)
        cached = self._runs.get(key)
        if cached is not None:
            return cached
        ctx = self._context_for(run)
        result = self._core.run_analysis(ctx, self._scenario(scenario_id), adaptation)
        self._remember(self._runs, key, result)
        return result

    # -- operaciones del puerto ----------------------------------------------------------------
    def run_base_analysis(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.dto import run_summary_dto
        from milpa_core.enums import AdaptationMode

        if request.get("parcel_id") is not None:
            raise self._pending(
                "corrida con parcela",
                "SoilContext desde el suelo declarado/medido de la parcela no está cableado",
            )
        if not request.get("zone_id"):
            raise ValidationFailed("La corrida base requiere zone_id")
        zone_id = UUID(str(request["zone_id"]))
        seed = int(request.get("seed", 0))
        start = _iso(request.get("period_start"))
        end = _iso(request.get("period_end"))
        ctx, info = self._build_context(zone_id, seed, start, end)
        base = self._core.run_analysis(ctx, self._core.BASE, AdaptationMode.NONE)
        from milpa_core.serialize import to_jsonable

        summary = run_summary_dto(base, ctx.strategies)
        summary["warnings"] = list(ctx.warnings)
        et0_parity = _et0_parity(info, ctx)
        if et0_parity is not None:
            summary["et0_parity_vs_R1"] = et0_parity
        return {
            "run": {
                "mode": base.decision.mode.value,
                "label": base.decision.label.value,
                "mode_reasons": list(base.decision.reasons),
                "data_hash": ctx.data_hash,
                "region_config_hash": ctx.region_config_hash,
                "catalog_hash": ctx.catalogs.catalog_hash,
                "code_version": self._core.ENGINE_VERSION,
                "seed": seed,
                "sandbox": ctx.region.status == "sandbox",
                "period": base.meta["period"],
                "n_cycle_results": len(base.cycle_results),
                "curated": to_jsonable(
                    {
                        "cell_id": info.cell_id,
                        "n_days": info.n_days,
                        "missing_pct": info.missing_pct,
                        "notes": info.notes,
                    }
                ),
            },
            "summary": summary,
        }

    def run_scenarios(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ctx = self._context_for(run)
        wanted = request.get("scenario_ids")
        grid = self._core.standard_grid()
        if wanted is not None:
            known = {sc.scenario_id: sc for sc in grid}
            unknown = sorted(set(wanted) - set(known))
            if unknown:
                raise NotFound(f"Escenarios fuera de la grilla de R2: {unknown}")
            grid = [known[i] for i in wanted]
        adaptations = [self._adaptation(a) for a in (request.get("adaptation_modes") or ["none"])]
        runs, skipped = self._core.run_grid(ctx, grid, adaptations)
        out: list[dict[str, Any]] = []
        for (sid, ad), result in runs.items():
            self._remember(self._runs, (run.run_id, sid, ad), result)
            out.append(
                {
                    "scenario_id": sid,
                    "adaptation_mode": ad,
                    "status": "ok",
                    "n_rows": len(result.cycle_results),
                    "grid_role": result.scenario.grid_role,
                }
            )
        for (sid, ad), reason in skipped.items():
            out.append(
                {
                    "scenario_id": sid,
                    "adaptation_mode": ad,
                    "status": "skipped",
                    "reason": reason,
                    "n_rows": 0,
                }
            )
        return {"engine_version": self._core.ENGINE_VERSION, "scenarios": out}

    def _rank_payload(
        self, run: RunRef, request: Mapping[str, Any]
    ) -> tuple[Any, Any, dict[str, Any]]:
        from milpa_core.enums import Criterion

        ctx = self._context_for(run)
        result = self._result(
            run,
            str(request.get("scenario_id") or "BASE"),
            self._adaptation(request.get("adaptation_mode")),
        )
        weights = request.get("weights")
        w = {Criterion(k): float(v) for k, v in weights.items()} if weights else None
        cfg = ctx.ranking_cfg
        if request.get("missing_policy"):
            cfg = replace(cfg, missing_policy=request["missing_policy"])
        ranking, extra = self._core.rank(ctx, result, w, cfg)
        return ctx, (ranking, extra), {"result": result}

    def rank(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.dto import rank_response_dto

        ctx, (ranking, extra), _ = self._rank_payload(run, request)
        stab = request.get("stability") or {}
        scfg = ctx.stability_cfg
        overrides = {
            k: stab[k]
            for k in ("n_samples", "mode", "concentration", "radius", "seed")
            if stab.get(k) is not None
        }
        scfg = replace(scfg, **overrides)
        stability = self._core.rank_stability(ranking, scfg)
        payload = dict(rank_response_dto(ranking, stability, extra))
        payload["anchors"] = extra["anchors"]
        return payload

    def soil_voi(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.serialize import to_jsonable

        ctx, (ranking, _), parts = self._rank_payload(run, request)
        voi = self._core.soil_voi(ctx, parts["result"], ranking)
        return _as_dict(to_jsonable(voi))

    def build_report(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.serialize import to_jsonable

        summary = self.summary(run, request)
        ranking = self.rank(
            run,
            {
                "scenario_id": request.get("scenario_id", "BASE"),
                "adaptation_mode": request.get("adaptation_mode", "none"),
                "weights": request.get("weights"),
                "missing_policy": request.get("missing_policy"),
                "stability": request.get("stability") or {},
            },
        )
        voi = self.soil_voi(run, request)
        report = self._core.build_report(dict(summary), dict(ranking), dict(voi), None)
        return _as_dict(to_jsonable(report))

    def summary(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.dto import run_summary_dto

        ctx = self._context_for(run)
        result = self._result(
            run, str(params.get("scenario") or "BASE"), self._adaptation(params.get("adaptation"))
        )
        return dict(run_summary_dto(result, ctx.strategies))

    @staticmethod
    def _provenance_by_strategy(ctx: Any, result: Any) -> dict[str, Any]:
        """Procedencia que R2 asigna al indicador principal de cada estrategia (para gráficos)."""
        from milpa_core.dto import run_summary_dto

        return {
            s["strategy"]: s["cohort_freq_critical"]["provenance"]
            for s in run_summary_dto(result, ctx.strategies)["strategies"]
        }

    def heatmap(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        from milpa_core.planting import consistent_windows, heatmap_cycle, heatmap_strategy
        from milpa_core.serialize import to_jsonable

        ctx = self._context_for(run)
        result = self._result(
            run, str(params.get("scenario") or "BASE"), self._adaptation(params.get("adaptation"))
        )
        heat: dict[str, Any] = {}
        for strategy in ctx.strategies:
            sweep = strategy.sweep_cycle()
            if sweep is None:
                continue
            by_cycle = heatmap_cycle(list(result.cycle_results), strategy.code, sweep.cycle_idx)
            by_strategy = heatmap_strategy(list(result.strategy_risk), strategy.code)
            p90 = [
                next(
                    (
                        c.stats["severity_p90_mm"]
                        for c in result.cycle_risk
                        if c.strategy == strategy.code
                        and c.cycle_idx == sweep.cycle_idx
                        and c.anchor_md == day
                    ),
                    None,
                )
                for day in by_cycle["plant_md"]
            ]
            by_cycle["consistent_windows"] = consistent_windows(
                by_cycle["plant_md"], by_cycle["pct_critical_by_date"], p90
            )
            heat[strategy.code] = {"cycle": by_cycle, "strategy": by_strategy}
        return _as_dict(
            to_jsonable(
                {
                    "mode": result.decision.mode.value,
                    "label": result.decision.label.value,
                    "scenario": result.tag,
                    "heatmaps": heat,
                    "provenance_by_strategy": self._provenance_by_strategy(ctx, result),
                }
            )
        )

    def dekad_chart(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        """Gráfico por decena. Con ``strategy`` (+ ``cohort_year``, ``cycle``, ``plant_date``) devuelve
        la cohorte pedida; sin filtros, la primera cohorte de cada estrategia (como ``r2_run``)."""
        from milpa_core.exposure import dekad_chart
        from milpa_core.serialize import to_jsonable
        from milpa_core.strategy import enumerate_cohorts

        ctx = self._context_for(run)
        result = self._result(
            run, str(params.get("scenario") or "BASE"), self._adaptation(params.get("adaptation"))
        )
        series = ctx.climate
        wanted = params.get("strategy")
        strategies = [s for s in ctx.strategies if wanted in (None, s.code)]
        if wanted is not None and not strategies:
            raise NotFound(f"Estrategia '{wanted}' no existe en la corrida")
        year = params.get("cohort_year")
        cycle = params.get("cycle")
        plant = params.get("plant_date")
        charts: dict[str, Any] = {}
        for strategy in strategies:
            cohorts = enumerate_cohorts(
                strategy, ctx.region, ctx.catalogs, series.dates[0], series.dates[-1]
            )
            instances = [ci for ch in cohorts for ci in ch.cycles if ci.harvest_date is not None]
            if wanted is not None:
                instances = [
                    ci
                    for ci in instances
                    if (year is None or ci.cohort_year == int(year))
                    and (cycle is None or ci.cycle_idx == int(cycle))
                    and (plant is None or str(ci.plant_date) == str(plant))
                ]
            if not instances:
                continue
            chart = dekad_chart(instances[0], result.climate, ctx.catalogs, ctx.region)
            chart["scenario"] = result.tag
            chart["provenance_info"] = self._provenance_by_strategy(ctx, result).get(strategy.code)
            charts[strategy.code] = chart
        if wanted is not None:
            if wanted not in charts:
                raise NotFound("No hay un ciclo evaluado con esa cohorte, ciclo y fecha de siembra")
            return _as_dict(to_jsonable(charts[wanted]))
        return _as_dict(to_jsonable(charts))

    def cycle_table(self, run: RunRef, scenario_id: str, adaptation: str) -> list[dict[str, Any]]:
        """Una fila por ciclo evaluado (valores tal como los calcula el motor)."""
        result = self._result(run, scenario_id, self._adaptation(adaptation))
        rows: list[dict[str, Any]] = []
        for r in result.cycle_results:
            rows.append(
                {
                    "strategy": r.strategy,
                    "cohort_year": r.cohort_year,
                    "cycle_idx": r.cycle_idx,
                    "variety": r.variety,
                    "anchor_md": r.anchor_md,
                    "plant_date": None if r.plant_date is None else str(r.plant_date),
                    "harvest_date": None if r.harvest_date is None else str(r.harvest_date),
                    "agri_year": r.agri_year,
                    "state": r.state.value,
                    "provisional": r.provisional,
                    "reason": ";".join(r.reasons),
                    "exposure_mm": r.severity_mm,
                    "missing_pct": None
                    if r.evaluability is None
                    else r.evaluability.missing_precip_pct,
                    "state_low": r.state_by_level["low"].value,
                    "state_high": r.state_by_level["high"].value,
                }
            )
        return rows

    def climate_history(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        """Totales anuales de lluvia observada y ET0 del motor, por año calendario completo.

        Descriptivo (sumas de la serie curada; sin modelar nada nuevo). Los años con menos de 90 %
        de días válidos se informan con su cobertura pero sin total (no se promedia con huecos).
        """
        import numpy as np
        from milpa_core.serialize import to_jsonable

        ctx = self._context_for(run)
        series = ctx.climate
        et0 = ctx.base_climate.et0_mm
        years_of_day = series.dates.astype("datetime64[Y]").astype(int) + 1970
        rows: list[dict[str, Any]] = []

        def indicator(
            code: str, label: str, value: float | None, unit: str, prov: Any
        ) -> dict[str, Any]:
            return {
                "code": code,
                "label_es": label,
                "label_en": label,
                "value": value,
                "unit": unit,
                "kind": "climate_input",
                "provisional": True,
                "reason": "Serie sandbox: evidencia C hasta validar con estación local",
                "provenance": to_jsonable(prov),
            }

        for year in sorted({int(y) for y in years_of_day}):
            mask = years_of_day == year
            rain = series.precip_mm[mask]
            valid = int(np.isfinite(rain).sum())
            complete = valid >= 0.9 * int(mask.sum())
            rain_total = float(np.nansum(rain)) if complete else None
            et0_year = et0[mask]
            et0_total = (
                float(np.nansum(et0_year)) if complete and np.isfinite(et0_year).any() else None
            )
            rows.append(
                {
                    "year": year,
                    "precip_mm": indicator(
                        "annual_precip_mm",
                        "Precipitación anual",
                        rain_total,
                        "mm",
                        series.precip_prov,
                    ),
                    "et0_mm": indicator(
                        "annual_et0_mm", "ET0 anual (FAO-56)", et0_total, "mm", series.met_prov
                    ),
                    "n_valid_days": indicator(
                        "valid_days",
                        "Días válidos de lluvia",
                        float(valid),
                        "días",
                        series.precip_prov,
                    ),
                }
            )
        out = _as_dict(
            to_jsonable(
                {
                    "years": rows,
                    "trends": [],
                    "provenance": series.precip_prov,
                    "message": None if rows else "Sin datos en el periodo de la corrida",
                }
            )
        )
        return out


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"milpa_core devolvió {type(value).__name__}; se esperaba un objeto")
    return value


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _et0_parity(info: core_io.CuratedInfo, ctx: Any) -> dict[str, Any] | None:
    """Control de paridad ET0 motor vs R1 (solo informa; no altera resultados)."""
    import numpy as np

    r1 = info.r1_et0_mm
    if r1 is None or not np.isfinite(r1).any():
        return None
    engine = ctx.base_climate.et0_mm
    ok = np.isfinite(r1) & np.isfinite(engine)
    if not ok.any():
        return None
    return {"mean_abs_diff_mm": float(np.mean(np.abs(r1[ok] - engine[ok]))), "n": int(ok.sum())}
