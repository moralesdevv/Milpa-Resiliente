import { StationValidationNotice } from "../components/zone/StationValidationNotice";
import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useClimateHistory, useHeatmap, useRank, useRun, useRunScenarios, useRunSummary, useZone, useZoneDataQuality } from "../api/queries";
import type { components } from "../api/types.gen";
import { ClimateHistory } from "../components/charts/ClimateHistory";
import { HeroArt } from "../components/common/HeroArt";
import { Heatmap } from "../components/charts/Heatmap";
import { PositionInversions } from "../components/charts/PositionInversions";
import { StabilityMeter } from "../components/charts/StabilityMeter";
import { Empty, ErrorState, InsufficientData, Loading } from "../components/common/states";
import { Indicator } from "../components/indicator/Indicator";
import { RunHeader } from "../components/run/RunHeader";
import { ScenarioBadge, ScenarioPicker, scenarioKey } from "../components/scenario/ScenarioComponents";
import { StrategyCompare } from "../components/scenario/StrategyCompare";
import { DataQualityBlock, ZoneContextBlock } from "../components/zone/ZoneComponents";
import { SourceStatus } from "../components/zone/SourceStatus";
import { buildInsights, strategyFamily } from "../lib/insights";
import { useSharedQueryParam } from "./ScreenFrame";

type RankRequest = components["schemas"]["RankRequest"];

const pretty = (code: string) => code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const EQUAL_WEIGHTS = { water: 0.25, soil: 0.25, food: 0.25, income: 0.25 };

const STEPS = [
  { n: "1", title: "Satellite & reanalysis", text: "NASA POWER (temperature, humidity, wind, radiation) and GPM IMERG (rainfall)" },
  { n: "2", title: "Curated daily series", text: "Quality-checked, gaps kept as gaps, every figure with its source" },
  { n: "3", title: "Scientific engine", text: "FAO-56 ET0 · effective rain · crop stages · exposure per cycle" },
  { n: "4", title: "Strategy comparison", text: "Robust risk, ranking on evidenced criteria, stability, 45 synthetic scenarios" },
  { n: "5", title: "Decision report", text: "What is decided, with what evidence, and what is still unknown" },
] as const;

/**
 * "MVP": the central workspace. It reads the same run, the same scenario and the same engine results the
 * detail screens use, and links into them keeping the shared parameters. It computes nothing itself:
 * every figure comes from the API (which comes from the engine) and carries its provenance.
 */
export function MvpScreen() {
  const [params, setParams] = useSearchParams();
  const [runId] = useSharedQueryParam("runId");
  const [strategyChoice, setStrategyChoice] = useSharedQueryParam("strategyId");
  const scenarioId = params.get("scenarioId") ?? "";

  const run = useRun(runId || null);
  const zoneId = run.data?.zone_id ?? null;
  const zone = useZone(zoneId);
  const quality = useZoneDataQuality(zoneId);
  const scenarios = useRunScenarios(runId || null);
  const selected = scenarios.data?.find((item) => item.scenario_id === scenarioId && item.adaptation_mode === "none")
    ?? scenarios.data?.find((item) => item.scenario_id === "BASE" && item.adaptation_mode === "none");
  const summary = useRunSummary(runId || null, selected?.scenario_id ?? null, "none");
  const history = useClimateHistory(runId || null);

  const rankRequest = useMemo<RankRequest | null>(() => selected
    ? { scenario_id: selected.scenario_id, adaptation_mode: "none", weights: EQUAL_WEIGHTS, missing_policy: "common_support", stability: { mode: "dirichlet", seed: 1 } }
    : null, [selected]);
  const ranking = useRank(runId || null, rankRequest);
  const baseScenario = scenarios.data?.find((item) => item.scenario_id === "BASE" && item.adaptation_mode === "none");
  const baseRankRequest = useMemo<RankRequest | null>(() => selected && baseScenario && selected.scenario_id !== "BASE"
    ? { scenario_id: "BASE", adaptation_mode: "none", weights: EQUAL_WEIGHTS, missing_policy: "common_support", stability: { mode: "dirichlet", seed: 1 } }
    : null, [selected, baseScenario]);
  const baseRanking = useRank(runId || null, baseRankRequest);

  const items = useMemo(() => summary.data?.items ?? [], [summary.data]);
  const focus = items.find((item) => item.strategy_version_id === strategyChoice) ?? items[0];
  const heatmap = useHeatmap(runId || null, { view: "strategy", strategy: focus?.strategy_version_id ?? null, scenario: selected?.scenario_id ?? null, adaptation: "none" });
  const insights = useMemo(() => buildInsights(items, ranking.data), [items, ranking.data]);

  useEffect(() => {
    if (!scenarioId && selected) {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set("scenarioId", selected.scenario_id);
        next.set("adaptation", "none");
        return next;
      }, { replace: true });
    }
  }, [scenarioId, selected, setParams]);

  const chooseScenario = (key: string) => {
    const match = scenarios.data?.find((item) => scenarioKey(item) === key);
    if (!match) return;
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set("scenarioId", match.scenario_id);
      next.set("adaptation", match.adaptation_mode);
      return next;
    }, { replace: true });
  };

  const keep = new URLSearchParams(params);
  keep.set("runId", runId);
  const to = (path: string) => `${path}?${keep.toString()}`;

  if (!runId) {
    return <div className="screen" data-screen="mvp">
      <header className="screen-heading">
      <HeroArt /><div className="screen-heading__text">
        <h1>MVP workspace</h1>
        <p className="screen-question">One place for the evidence, the strategies and the decision.</p>
      </div></header>
      <section className="content-card">
        <Empty title="No analysis is open" detail="Launch the demo to compute a real run on the pilot zone, or open a run identifier from the detail screens." />
        <p><Link className="button" to="/demo">Launch demo</Link></p>
      </section>
    </div>;
  }

  return <div className="screen mvp" data-screen="mvp">
    <header className="screen-heading">
      <HeroArt />
      <div className="screen-heading__text">
        <h1>MVP workspace</h1>
        <p className="screen-question">From satellite data to a planting decision: what we know, what it means for each strategy, and what is still uncertain.</p>
        <p className="screen-tag">{zone.data ? `Zone ${zone.data.name}` : "Zone"} · run <code>{runId.slice(0, 8)}</code></p>
      </div>
    </header>

    <nav className="mvp-jump" aria-label="Sections of this page">
      <a href="#evidence">Evidence</a><a href="#climate">Climate</a><a href="#strategies">Strategies</a><a href="#calendar">Planting calendar</a><a href="#limits">Limits</a><a href="#next">Go deeper</a>
    </nav>

    <RunHeader runId={runId} />

    <section className="content-card" id="how" aria-labelledby="how-title">
      <div className="section-heading"><h2 id="how-title">How this result was made</h2></div>
      <ol className="mvp-steps">{STEPS.map((step) => <li key={step.n}><b aria-hidden="true">{step.n}</b><div><strong>{step.title}</strong><span>{step.text}</span></div></li>)}</ol>
      {run.data && <dl className="mvp-facts">
        <div><dt>Period analysed</dt><dd>{run.data.period_start} → {run.data.period_end}</dd></div>
        <div><dt>Calculation mode</dt><dd>{run.data.mode === "exposure" ? "Climate-exposure indicator (no soil-water balance)" : "Root-zone water balance"}</dd></div>
        <div><dt>Engine</dt><dd>{run.data.code_version}</dd></div>
        <div><dt>Data hash</dt><dd><code>{run.data.data_hash.slice(0, 16)}…</code></dd></div>
        <div><dt>Seed</dt><dd>{run.data.seed}</dd></div>
      </dl>}
    </section>

    <section className="content-card" id="evidence" aria-labelledby="evidence-title">
      <div className="section-heading"><h2 id="evidence-title">Territory, crops and evidence: where the data come from</h2></div>
      {zone.isLoading && <Loading />}
      {zone.data && <ZoneContextBlock context={zone.data.context} />}
      {quality.isLoading && <Loading />}
      {quality.isError && <ErrorState error={quality.error} onRetry={() => void quality.refetch()} />}
      {quality.data && <DataQualityBlock quality={quality.data} sources={zone.data?.sources} />}
      <details className="chart-data-details"><summary>Every source contemplated by the project and its real status</summary><SourceStatus /></details>
    </section>

    <section className="content-card" id="climate" aria-labelledby="climate-title">
      <div className="section-heading"><h2 id="climate-title">Climate: how much it rained and what crops demand</h2></div>
      {zoneId && <StationValidationNotice zoneId={zoneId} />}
      {history.isLoading && <Loading />}
      {history.isError && <ErrorState error={history.error} onRetry={() => void history.refetch()} />}
      {history.data && <ClimateHistory history={history.data} />}
      <p className="chart-caption">Annual rainfall (bars) and reference evapotranspiration (line). Exposure is not an actual soil-water deficit.</p>
    </section>

    <section className="content-card" id="strategies" aria-labelledby="strategies-title">
      <div className="section-heading"><h2 id="strategies-title">Strategies: risk, trade-offs and what they plant</h2></div>
      {scenarios.data && <div className="mvp-scenario">
        <ScenarioPicker scenarios={scenarios.data} value={selected ? scenarioKey(selected) : ""} onChange={chooseScenario} />
        {selected && <ScenarioBadge scenario={selected} />}
      </div>}
      {summary.isLoading && <Loading />}
      {summary.isError && <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />}
      {items.length > 0 && <>
        <div className="mvp-reading" data-testid="mvp-reading">
          <h3>What the engine says</h3>
          <ul>{insights.findings.map((text) => <li key={text}>{text}</li>)}</ul>
          {insights.cautions.length > 0 && <ul className="mvp-cautions">{insights.cautions.map((text) => <li key={text}>{text}</li>)}</ul>}
        </div>
        <ul className="mvp-cards">{items.map((item) => {
          const crops = [...new Set(item.by_cycle.map((cycle) => pretty(String(cycle.variety_id))))];
          const rank = ranking.data?.ranking.find((row) => row.strategy_version_id === item.strategy_version_id);
          const water = item.water_inputs as Record<string, components["schemas"]["IndicatorNumber"] | undefined>;
          return <li key={item.strategy_version_id} className={`mvp-card${focus?.strategy_version_id === item.strategy_version_id ? " is-focus" : ""}`}>
            <div className="mvp-card__head">
              <span className="mvp-chip">{strategyFamily(item)}</span>
              {rank && <span className="mvp-rank" title="Position under equal priorities">#{rank.rank.value}</span>}
            </div>
            <h3>{item.name}</h3>
            <p className="mvp-crops">{crops.join(" → ")}</p>
            <dl>
              <div><dt>Critical cohorts</dt><dd><Indicator indicator={item.cohort_freq_critical} compact /></dd></div>
              {water.p90_severity_by_agri_year && <div><dt>Severity P90</dt><dd><Indicator indicator={water.p90_severity_by_agri_year} compact /></dd></div>}
            </dl>
            <p className="mvp-n">{String((item as { n_decided?: number }).n_decided ?? "?")} evaluable of {String((item as { n_independent_cohorts?: number }).n_independent_cohorts ?? "?")} independent cohorts</p>
            <button className="button button--secondary button--compact" type="button" onClick={() => setStrategyChoice(item.strategy_version_id)} aria-pressed={focus?.strategy_version_id === item.strategy_version_id}>Show planting calendar</button>
          </li>;
        })}</ul>
        {selected && items.length > 1 && <StrategyCompare strategies={items} ranking={ranking.data ?? null} scenarioLabel={selected.scenario_id} />}
        {ranking.isError && <ErrorState error={ranking.error} onRetry={() => void ranking.refetch()} />}
        {ranking.data && <StabilityMeter stability={ranking.data.stability} />}
        {selected && selected.scenario_id !== "BASE" && <div className="mvp-inversions"><PositionInversions base={baseRanking.data} selected={ranking.data ?? null} /></div>}
        <p className="chart-caption">Need another combination of temperature, rainfall, rain-onset delay or the adaptation reading? <Link to={to("/rotations")}>Compute it in the Rotation lab</Link>; scenarios are synthetic perturbations, not forecasts.</p>
      </>}
      {summary.data && items.length === 0 && <InsufficientData detail="No strategy results for this scenario." />}
    </section>

    <section className="content-card" id="calendar" aria-labelledby="calendar-title">
      <div className="section-heading"><h2 id="calendar-title">Planting calendar{focus ? `: ${focus.name}` : ""}</h2></div>
      <p className="chart-caption">Planting date × cohort year. Cells show whether a critical stage met critical exposure; the bottom row is the share of critical cohorts per date.</p>
      {heatmap.isLoading && <Loading />}
      {heatmap.isError && <ErrorState error={heatmap.error} onRetry={() => void heatmap.refetch()} />}
      {!heatmap.isLoading && !heatmap.isError && <Heatmap data={heatmap.data ?? null} />}
    </section>

    <section className="content-card" id="limits" aria-labelledby="limits-title">
      <div className="section-heading"><h2 id="limits-title">Limits and uncertainty, stated up front</h2></div>
      <ul className="mvp-limits">
        <li><strong>Rainfall evidence is level C.</strong> IMERG is a satellite product and has not been validated against a local weather station.</li>
        <li><strong>Thresholds and crop coefficients are provisional.</strong> Without a citation a threshold stays provisional; results are an indicator, not a verdict.</li>
        <li><strong>Exposure is not soil water.</strong> The root-zone balance needs measured soil properties and a declared starting condition; without them the engine does not run it.</li>
        <li><strong>Food and income are not evaluated.</strong> They need cited yields, prices and food composition; the ranking excludes them for every strategy instead of guessing.</li>
        <li><strong>Scenarios are synthetic perturbations of the historical series.</strong> They are not forecasts and not CMIP6 projections.</li>
        <li><strong>Not an automatic recommendation.</strong> What to plant, when and with which priorities remains a human decision.</li>
      </ul>
    </section>

    <section className="content-card" id="next" aria-labelledby="next-title">
      <div className="section-heading"><h2 id="next-title">Go deeper</h2></div>
      <ul className="mvp-links">
        <li><Link to={to("/my-zone")}><strong>My zone</strong><span>Territory, sources, soil by property, value of soil information</span></Link></li>
        <li><Link to={to("/calendar")}><strong>How the calendar changed</strong><span>25-year history, dekad chart, planting heat-map</span></Link></li>
        <li><Link to={to("/rotations")}><strong>Rotation lab</strong><span>Scenarios, priorities, ranking and stability</span></Link></li>
        <li><Link to={to("/plants")}><strong>Plants</strong><span>Crops per strategy and their critical growth stages</span></Link></li>
        <li><Link to={to("/report")}><strong>Decision report</strong><span>The evidence, assumptions and what to verify in the field</span></Link></li>
      </ul>
    </section>
  </div>;
}
