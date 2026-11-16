import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { useClimateHistory, useDekadChart, useHeatmap, useRunScenarios, useRunSummary } from "../api/queries";
import { Empty, ErrorState, InsufficientData, Loading } from "../components/common/states";
import { ClimateHistory } from "../components/charts/ClimateHistory";
import { DekadChart } from "../components/charts/DekadChart";
import { RunHeader } from "../components/run/RunHeader";
import { Heatmap } from "../components/charts/Heatmap";
import { RiskCards } from "../components/charts/RiskCards";
import { ScenarioBadge, ScenarioPicker, scenarioKey } from "../components/scenario/ScenarioComponents";
import { RunIdField, ScreenFrame, useSharedQueryParam } from "./ScreenFrame";
import { Icon } from "../components/common/Icon";

export function CalendarScreen() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [runId, setRunId] = useSharedQueryParam("runId");
  const scenarioId = params.get("scenarioId") ?? "";
  const adaptationValue = params.get("adaptation") ?? "none";
  const [strategyId, setStrategyId] = useSharedQueryParam("strategyId");
  const [viewValue, setView] = useSharedQueryParam("heatmapView", "strategy");
  const [cycleValue, setCycle] = useSharedQueryParam("cycleIdx");
  const [varietyId, setVarietyId] = useSharedQueryParam("varietyId");
  const [cohortYearValue, setCohortYear] = useSharedQueryParam("cohortYear");
  const [plantDateValue, setPlantDate] = useSharedQueryParam("plantDate");
  const adaptation = adaptationValue === "onset_rule" ? "onset_rule" : "none";
  const view = viewValue === "cycle" ? "cycle" : "strategy";

  const scenarios = useRunScenarios(runId || null);
  const selectedScenario = scenarios.data?.find((scenario) => scenario.scenario_id === scenarioId && scenario.adaptation_mode === adaptation);
  const baseScenario = scenarios.data?.find((scenario) => scenario.scenario_id === "BASE" && scenario.adaptation_mode === selectedScenario?.adaptation_mode);
  const summary = useRunSummary(runId || null, selectedScenario?.scenario_id ?? null, adaptation);
  const baseSummary = useRunSummary(runId || null, baseScenario?.scenario_id ?? null, baseScenario?.adaptation_mode ?? "none");
  const climateHistory = useClimateHistory(runId || null);
  const selectedStrategy = summary.data?.items.find((item) => item.strategy_version_id === strategyId) ?? summary.data?.items[0];
  const cycleRows = selectedStrategy?.by_cycle ?? [];
  const cycleOptions = [...new Set(cycleRows.map((item) => item.cycle_idx))];
  const rowsForCycle = cycleRows.filter((item) => String(item.cycle_idx) === cycleValue);
  const currentCycleRows = rowsForCycle.length ? rowsForCycle : cycleRows.filter((item) => item.cycle_idx === cycleOptions[0]);
  const selectedCycle = currentCycleRows.find((item) => item.variety_id === varietyId) ?? currentCycleRows[0];
  const cycle = selectedCycle?.cycle_idx;
  const varieties = [...new Set(currentCycleRows.map((item) => item.variety_id))];
  const selectedVariety = varieties.includes(varietyId) ? varietyId : selectedCycle?.variety_id;
  const heatmap = useHeatmap(runId || null, {
    view,
    strategy: selectedStrategy?.strategy_version_id ?? null,
    cycle: view === "cycle" ? cycle : undefined,
    variety: selectedVariety,
    scenario: selectedScenario?.scenario_id ?? null,
    adaptation,
  });
  const cohortYear = heatmap.data?.years.find((year) => String(year) === cohortYearValue) ?? heatmap.data?.years[0];
  const plantDate = heatmap.data?.plant_md.includes(plantDateValue) ? plantDateValue : heatmap.data?.plant_md[0];
  const dekadChart = useDekadChart(runId || null, {
    strategy: selectedStrategy?.strategy_version_id ?? null,
    cohortYear,
    cycle,
    plantDate,
    scenario: selectedScenario?.scenario_id ?? null,
  });

  const selectedStrategyKey = selectedStrategy?.strategy_version_id;
  const selectedCycleKey = selectedCycle?.cycle_idx;

  useEffect(() => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      let changed = false;
      if (selectedStrategyKey && selectedStrategyKey !== strategyId) {
        next.set("strategyId", selectedStrategyKey);
        changed = true;
      }
      if (selectedCycleKey !== undefined && String(selectedCycleKey) !== cycleValue) {
        next.set("cycleIdx", String(selectedCycleKey));
        changed = true;
      }
      if (selectedVariety && selectedVariety !== varietyId) {
        next.set("varietyId", selectedVariety);
        changed = true;
      }
      if (cohortYear !== undefined && String(cohortYear) !== cohortYearValue) {
        next.set("cohortYear", String(cohortYear));
        changed = true;
      }
      if (plantDate && plantDate !== plantDateValue) {
        next.set("plantDate", plantDate);
        changed = true;
      }
      return changed ? next : current;
    }, { replace: true });
  }, [selectedStrategyKey, strategyId, selectedCycleKey, cycleValue, selectedVariety, varietyId, cohortYear, cohortYearValue, plantDate, plantDateValue, setParams]);

  const chooseScenario = (key: string) => {
    const scenario = scenarios.data?.find((item) => scenarioKey(item) === key);
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (scenario) {
        next.set("scenarioId", scenario.scenario_id);
        next.set("adaptation", scenario.adaptation_mode);
      } else {
        next.delete("scenarioId");
        next.delete("adaptation");
      }
      return next;
    }, { replace: true });
  };

  return <ScreenFrame id="calendar">
    <section className="filter-panel" aria-labelledby="calendar-filters">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="filter" /></span><h2 id="calendar-filters">{t("screens.calendar.filters")}</h2></div>
      <div className="filter-grid">
        <RunIdField value={runId} onChange={setRunId} />
        {scenarios.isLoading && <Loading />}
        {scenarios.isError && <ErrorState error={scenarios.error} onRetry={() => void scenarios.refetch()} />}
        {scenarios.data && <ScenarioPicker scenarios={scenarios.data} value={selectedScenario ? scenarioKey(selectedScenario) : ""} onChange={chooseScenario} />}
        <label className="field"><span>{t("calendar.view")}</span>
          <select value={view} onChange={(event) => setView(event.currentTarget.value)}>
            <option value="strategy">{t("calendar.views.strategy")}</option>
            <option value="cycle">{t("calendar.views.cycle")}</option>
          </select>
        </label>
        <label className="field"><span>{t("calendar.strategy")}</span>
          <select value={selectedStrategy?.strategy_version_id ?? ""} onChange={(event) => setStrategyId(event.currentTarget.value)} disabled={!summary.data?.items.length}>
            {summary.data?.items.map((item) => <option key={item.strategy_version_id} value={item.strategy_version_id}>{item.name}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("calendar.cycle")}</span>
          <select value={cycle ?? ""} onChange={(event) => setCycle(event.currentTarget.value)} disabled={!selectedStrategy} aria-describedby="cycle-filter-help">
            {cycleOptions.map((cycleIndex) => <option key={cycleIndex} value={cycleIndex}>{t("calendar.cycle")} {cycleIndex}</option>)}
          </select>
          <small id="cycle-filter-help">{t("calendar.view")} · {t("calendar.views.cycle")}</small>
        </label>
        <label className="field"><span>{t("calendar.variety")}</span>
          <select value={selectedVariety ?? ""} onChange={(event) => setVarietyId(event.currentTarget.value)} disabled={varieties.length === 0}>
            {varieties.map((id) => <option value={id} key={id}>{id}</option>)}
          </select>
        </label>
      </div>
      {!runId && <InsufficientData title={t("forms.selectRun")} detail={t("forms.noRuns")} />}
      {runId && !scenarios.isLoading && !scenarios.isError && scenarios.data?.length === 0 && <Empty title={t("scenario.noneComputed")} detail={t("scenario.notComputedHint")} />}
    </section>

    {runId && <RunHeader runId={runId} />}

    <section className="content-card" aria-labelledby="history-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="history" /></span><h2 id="history-heading">{t("calendar.climateHistory")}</h2></div>
      {climateHistory.isLoading && <Loading />}
      {climateHistory.isError && <ErrorState error={climateHistory.error} onRetry={() => void climateHistory.refetch()} />}
      {climateHistory.data && <ClimateHistory history={climateHistory.data} />}
      {!runId && <Empty title={t("forms.selectRun")} detail={t("forms.noRuns")} />}
      <p className="chart-caption">{t("common.notRealDeficit")}</p>
    </section>

    <section className="content-card" aria-labelledby="strategy-risk-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="risk" /></span><h2 id="strategy-risk-heading">{t("calendar.riskByStrategy")}</h2></div>
      {summary.isLoading && <Loading />}
      {summary.isError && <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />}
      {selectedScenario && <ScenarioBadge scenario={selectedScenario} />}
      {summary.data?.items.length ? <RiskCards strategies={summary.data.items} /> : null}
      {summary.data && summary.data.items.length === 0 && <InsufficientData detail={t("common.insufficientData")} />}
      {!selectedScenario && runId && <InsufficientData detail={t("scenario.selectOne")} />}
    </section>

    <section className="content-card" aria-labelledby="base-comparison-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="compare" /></span><h2 id="base-comparison-heading">{t("calendar.baseReference")}</h2></div>
      <p className="chart-caption">{t("calendar.comparisonNote")}</p>
      {!selectedScenario && <Empty title={t("scenario.selectOne")} />}
      {selectedScenario && selectedScenario.scenario_id === "BASE" && <Empty title={t("calendar.baseReference")} detail={t("calendar.baseSelected")} />}
      {selectedScenario && selectedScenario.scenario_id !== "BASE" && !baseScenario && <Empty title={t("calendar.baseComparison")} detail={t("scenario.notComputedHint")} />}
      {baseSummary.isLoading && <Loading />}
      {baseSummary.isError && <ErrorState error={baseSummary.error} onRetry={() => void baseSummary.refetch()} />}
      {baseScenario && selectedScenario?.scenario_id !== "BASE" && <div className="scenario-comparison">
        <article className="comparison-column">
          <h3>{t("calendar.selectedScenario")}</h3><ScenarioBadge scenario={selectedScenario!} />
          {summary.data?.items.length ? <RiskCards strategies={summary.data.items} /> : <InsufficientData detail={t("common.insufficientData")} />}
        </article>
        <article className="comparison-column">
          <h3>{t("calendar.baseReference")}</h3><ScenarioBadge scenario={baseScenario} />
          {baseSummary.data?.items.length ? <RiskCards strategies={baseSummary.data.items} /> : baseSummary.data ? <InsufficientData detail={t("common.insufficientData")} /> : null}
        </article>
      </div>}
    </section>

    <section className="content-card" aria-labelledby="dekad-filters-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="location" /></span><h2 id="dekad-filters-heading">{t("calendar.dekadSelection")}</h2></div>
      <div className="filter-grid">
        <label className="field"><span>{t("calendar.cohortYear")}</span>
          <select value={cohortYear ?? ""} onChange={(event) => setCohortYear(event.currentTarget.value)} disabled={!heatmap.data?.years.length}>
            {heatmap.data?.years.map((year) => <option value={year} key={year}>{year}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("calendar.date")}</span>
          <select value={plantDate ?? ""} onChange={(event) => setPlantDate(event.currentTarget.value)} disabled={!heatmap.data?.plant_md.length}>
            {heatmap.data?.plant_md.map((date) => <option value={date} key={date}>{date}</option>)}
          </select>
        </label>
      </div>
    </section>

    <div className="chart-layout">
      {heatmap.isLoading && <Loading />}
      {heatmap.isError && <ErrorState error={heatmap.error} onRetry={() => void heatmap.refetch()} />}
      {!heatmap.isLoading && !heatmap.isError && <Heatmap data={heatmap.data ?? null} />}
      {dekadChart.isLoading && <Loading />}
      {dekadChart.isError && <ErrorState error={dekadChart.error} onRetry={() => void dekadChart.refetch()} />}
      {!dekadChart.isLoading && !dekadChart.isError && <DekadChart data={dekadChart.data ?? null} />}
    </div>
  </ScreenFrame>;
}
