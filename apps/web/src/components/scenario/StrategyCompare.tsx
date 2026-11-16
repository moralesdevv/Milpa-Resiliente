import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";

import type { components } from "../../api/types.gen";
import { Indicator } from "../indicator/Indicator";
import { axisStyle, baseTextStyle, chartColors, chartMotion, legendStyle, valueAxisStyle } from "../charts/chartTheme";

type Strategy = components["schemas"]["StrategyRiskDTO"];
type Rank = components["schemas"]["RankResponse"];

const MAX_SELECTED = 4;
const consistencyLabel: Record<string, string> = {
  consistente: "Consistent",
  variable: "Variable",
  fallos_en_años_desfavorables: "Fails in unfavourable years",
  no_comparable: "Not comparable",
};

/**
 * Side-by-side comparison of 2–4 strategies chosen by the user, for the scenario selected above.
 * It only arranges figures the engine already produced (risk summary and ranking); nothing is computed here.
 */
export function StrategyCompare({ strategies, ranking, scenarioLabel }: { strategies: Strategy[]; ranking: Rank | null; scenarioLabel: string }) {
  const [picked, setPicked] = useState<string[]>([]);
  const selected = useMemo(() => {
    const ids = picked.length ? picked : strategies.slice(0, 2).map((item) => item.strategy_version_id);
    return strategies.filter((item) => ids.includes(item.strategy_version_id));
  }, [picked, strategies]);

  const toggle = (id: string) => {
    const current = selected.map((item) => item.strategy_version_id);
    if (current.includes(id)) setPicked(current.filter((item) => item !== id));
    else if (current.length < MAX_SELECTED) setPicked([...current, id]);
  };

  const rankOf = (id: string) => ranking?.ranking.find((row) => row.strategy_version_id === id);
  const p90 = (item: Strategy) => (item.water_inputs as Record<string, components["schemas"]["IndicatorNumber"] | undefined>).p90_severity_by_agri_year;
  const worst = (item: Strategy) => item.by_cycle.map((cycle) => cycle.worst_year_severity).filter(Boolean).sort((a, b) => (b.value ?? 0) - (a.value ?? 0))[0];

  const option = useMemo<EChartsOption>(() => ({
    aria: { enabled: true, description: "Critical-cohort frequency and 90th-percentile severity for the selected strategies" },
    ...chartMotion(),
    textStyle: baseTextStyle,
    grid: { left: 48, right: 56, top: 48, bottom: 56, containLabel: true },
    legend: { ...legendStyle, data: ["Critical-cohort frequency (%)", "P90 severity (mm)"] },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: selected.map((item) => item.name), ...axisStyle, axisLabel: { ...(axisStyle as { axisLabel?: object }).axisLabel, interval: 0, width: 110, overflow: "break" } },
    yAxis: [
      { type: "value", name: "%", ...valueAxisStyle },
      { type: "value", name: "mm", ...valueAxisStyle, splitLine: { show: false } },
    ],
    series: [
      { name: "Critical-cohort frequency (%)", type: "bar", barMaxWidth: 36, data: selected.map((item) => item.cohort_freq_critical.value), itemStyle: { color: chartColors.demand, borderRadius: [3, 3, 0, 0] } },
      { name: "P90 severity (mm)", type: "bar", barMaxWidth: 36, yAxisIndex: 1, data: selected.map((item) => p90(item)?.value ?? null), itemStyle: { color: chartColors.water, borderRadius: [3, 3, 0, 0] } },
    ],
  }), [selected]);

  return <div className="strategy-compare" data-testid="strategy-compare">
    <p className="chart-caption">Pick up to {MAX_SELECTED} strategies. Scenario: <strong>{scenarioLabel}</strong>. Differences are shown as the engine reports them; this is not a recommendation.</p>
    <fieldset className="compare-picker">
      <legend>Strategies to compare</legend>
      {strategies.map((item) => {
        const checked = selected.some((candidate) => candidate.strategy_version_id === item.strategy_version_id);
        return <label key={item.strategy_version_id} className={`compare-chip${checked ? " is-selected" : ""}`}>
          <input type="checkbox" checked={checked} disabled={!checked && selected.length >= MAX_SELECTED} onChange={() => toggle(item.strategy_version_id)} />
          <span>{item.name}</span>
        </label>;
      })}
    </fieldset>
    {selected.length < 2 && <p className="chart-caption" role="status">Select at least two strategies to compare them.</p>}
    {selected.length >= 2 && <>
      <div className="chart-canvas" role="img" aria-label="Comparison of the selected strategies">
        <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge lazyUpdate />
      </div>
      <div className="table-scroll"><table className="data-table compare-table">
        <caption>Selected strategies, same scenario</caption>
        <thead><tr><th scope="col">Measure</th>{selected.map((item) => <th scope="col" key={item.strategy_version_id}>{item.name}</th>)}</tr></thead>
        <tbody>
          <tr><th scope="row">Critical-cohort frequency</th>{selected.map((item) => <td key={item.strategy_version_id}><Indicator indicator={item.cohort_freq_critical} compact /><small className="mvp-n">{String((item as { n_decided?: number }).n_decided ?? "?")} evaluable of {String((item as { n_independent_cohorts?: number }).n_independent_cohorts ?? "?")} cohorts</small></td>)}</tr>
          <tr><th scope="row">P90 severity</th>{selected.map((item) => <td key={item.strategy_version_id}>{p90(item) ? <Indicator indicator={p90(item)!} compact /> : "n/a"}</td>)}</tr>
          <tr><th scope="row">Worst-year severity</th>{selected.map((item) => <td key={item.strategy_version_id}>{worst(item) ? <Indicator indicator={worst(item)} compact /> : "n/a"}</td>)}</tr>
          <tr><th scope="row">Consistency</th>{selected.map((item) => <td key={item.strategy_version_id}>{consistencyLabel[String(item.consistency)] ?? String(item.consistency)}</td>)}</tr>
          <tr><th scope="row">Horizon</th>{selected.map((item) => <td key={item.strategy_version_id}>{item.horizon_years} {item.horizon_years === 1 ? "year" : "years"}{item.overlapping_cohorts ? " (overlapping cohorts)" : ""}</td>)}</tr>
          <tr><th scope="row">Changes from the reference</th>{selected.map((item) => <td key={item.strategy_version_id}>{item.changes_from_reference.length ? item.changes_from_reference.join(", ").replace(/_/g, " ") : "—"}</td>)}</tr>
          <tr><th scope="row">Rank under current weights</th>{selected.map((item) => <td key={item.strategy_version_id}>{rankOf(item.strategy_version_id) ? <>#{rankOf(item.strategy_version_id)!.rank.value} · score {rankOf(item.strategy_version_id)!.total.value?.toFixed(2)}</> : "n/a"}</td>)}</tr>
        </tbody>
      </table></div>
      {ranking && <p className="chart-caption">Rank uses only the criteria with evidence ({ranking.criteria_used.join(", ")}); the rest are not evaluable and never win by default.</p>}
    </>}
  </div>;
}
