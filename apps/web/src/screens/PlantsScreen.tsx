import { Link } from "react-router-dom";

import { useDekadChart, useHeatmap, useRunSummary } from "../api/queries";
import { Empty, ErrorState, InsufficientData, Loading } from "../components/common/states";
import { Indicator } from "../components/indicator/Indicator";
import { RunHeader } from "../components/run/RunHeader";
import { RunIdField, ScreenFrame, useSharedQueryParam } from "./ScreenFrame";

/** "maiz_corto" → "Maiz corto": variety codes come from the engine's crop catalog. */
const STAGES: Record<string, string> = { INI: "Initial", DEV: "Development", MID: "Mid-season", LATE: "Late season" };
const stageName = (code: string) => STAGES[code] ?? code;
const pretty = (code: string) => code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/**
 * Plants: the crops behind each strategy, built only from the run's own results —
 * which variety each cycle plants, how often it hits a critical water-stress outcome,
 * and the growth stages (with the critical ones) of the selected planting.
 */
export function PlantsScreen() {
  const [runId, setRunId] = useSharedQueryParam("runId");
  const [strategyId, setStrategyId] = useSharedQueryParam("strategyId");
  const summary = useRunSummary(runId || null, runId ? "BASE" : null, "none");
  const items = summary.data?.items ?? [];
  const selected = items.find((item) => item.strategy_version_id === strategyId) ?? items[0];
  const cycles = selected?.by_cycle ?? [];
  const firstCycle = cycles[0];

  const heatmap = useHeatmap(runId || null, { view: "strategy", strategy: selected?.strategy_version_id ?? null, scenario: runId ? "BASE" : null, adaptation: "none" });
  const year = heatmap.data?.years[0];
  const plantDate = heatmap.data?.plant_md[0];
  const dekad = useDekadChart(runId || null, {
    strategy: selected?.strategy_version_id ?? null,
    cohortYear: year,
    cycle: firstCycle?.cycle_idx,
    plantDate: year && plantDate ? `${year}-${plantDate}` : undefined,
    scenario: runId ? "BASE" : null,
  });

  const bands = dekad.data?.stage_bands ?? [];
  const spanStart = bands.length ? Date.parse(bands[0].start) : 0;
  const spanEnd = bands.length ? Date.parse(bands[bands.length - 1].end) : 1;
  const pct = (iso: string) => `${(((Date.parse(iso) - spanStart) / Math.max(spanEnd - spanStart, 1)) * 100).toFixed(2)}%`;

  return <ScreenFrame id="plants">
    <section className="filter-panel" aria-labelledby="plants-filters">
      <div className="section-heading"><h2 id="plants-filters">Choose a run and a strategy</h2></div>
      <div className="filter-grid">
        <RunIdField value={runId} onChange={setRunId} />
        <label className="field"><span>Strategy</span>
          <select value={selected?.strategy_version_id ?? ""} onChange={(event) => setStrategyId(event.currentTarget.value)} disabled={items.length === 0}>
            {items.map((item) => <option key={item.strategy_version_id} value={item.strategy_version_id}>{item.name}</option>)}
          </select>
        </label>
      </div>
      {!runId && <Empty title="No run selected" detail="Open the demo to compute a run, or paste a run identifier." />}
      {!runId && <p><Link className="button button--secondary" to="/demo">Launch demo</Link></p>}
    </section>

    {runId && <RunHeader runId={runId} />}
    {summary.isLoading && <Loading />}
    {summary.isError && <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />}

    {selected && <section className="content-card plants" aria-labelledby="plants-crops">
      <div className="section-heading"><h2 id="plants-crops">{selected.name}</h2></div>
      {selected.changes_from_reference.length > 0
        ? <p className="chart-caption">Differs from the reference strategy in: {selected.changes_from_reference.join(", ").replace(/_/g, " ")}.</p>
        : <p className="chart-caption">This is the reference strategy.</p>}
      <ul className="plants__cycles">
        {cycles.map((cycle) => <li key={`${cycle.cycle_idx}:${cycle.variety_id}`} className="plants__cycle">
          <div className="plants__crop">
            <svg viewBox="0 0 64 96" width="48" height="72" aria-hidden="true" focusable="false" className="plants__icon">
              <path d="M32 94V18" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
              <path d="M32 70C14 68 6 56 6 40c16 2 24 12 26 30Z" fill="currentColor" opacity=".75" />
              <path d="M32 52C50 50 58 38 58 22c-16 2-24 12-26 30Z" fill="currentColor" opacity=".9" />
              <path d="M32 30c-8-2-12-8-12-16 8 1 12 7 12 16Z" fill="currentColor" />
            </svg>
            <div><h3>{pretty(cycle.variety_id)}</h3><p className="chart-caption">Cycle {cycle.cycle_idx}{cycle.anchor_md ? ` · reference planting ${cycle.anchor_md}` : ""}</p></div>
          </div>
          <dl className="plants__stats">
            <div><dt>Critical-cycle frequency</dt><dd><Indicator indicator={cycle.freq_critical} compact /></dd></div>
            <div><dt>Severity, 90th percentile</dt><dd><Indicator indicator={cycle.severity_p90} compact /></dd></div>
          </dl>
        </li>)}
      </ul>
    </section>}

    {selected && <section className="content-card" aria-labelledby="plants-stages">
      <div className="section-heading"><h2 id="plants-stages">Growth stages of the first planting</h2></div>
      {dekad.isLoading && <Loading />}
      {dekad.isError && <ErrorState error={dekad.error} onRetry={() => void dekad.refetch()} />}
      {dekad.data && bands.length > 0 && <>
        <p className="chart-caption">Cohort {dekad.data.cohort_year}, planted {dekad.data.plant_date}. Highlighted stages are the ones where the engine measures water-stress exposure.</p>
        <div className="stage-track" role="img" aria-label={`Growth stages: ${bands.map((band) => `${stageName(band.stage)}${band.critical ? " (critical)" : ""}`).join(", ")}`}>
          {bands.map((band) => <span key={band.stage} className={`stage-band${band.critical ? " stage-band--critical" : ""}`} style={{ left: pct(band.start), width: `${(((Date.parse(band.end) - Date.parse(band.start)) / Math.max(spanEnd - spanStart, 1)) * 100).toFixed(2)}%` }}>
            <b>{stageName(band.stage)}</b><small>{band.start.slice(5)} → {band.end.slice(5)}</small>
          </span>)}
        </div>
        <p><Link className="button button--secondary" to={`/calendar?runId=${encodeURIComponent(runId)}&scenarioId=BASE&adaptation=none&strategyId=${encodeURIComponent(selected.strategy_version_id)}`}>See this strategy in the calendar</Link></p>
      </>}
      {!dekad.isLoading && !dekad.isError && bands.length === 0 && <InsufficientData detail="No evaluated planting with growth stages is available for this selection." />}
    </section>}
  </ScreenFrame>;
}
