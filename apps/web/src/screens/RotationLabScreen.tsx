import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { useRank, useRunScenarios, useRunSummary } from "../api/queries";
import type { components } from "../api/types.gen";
import { PositionInversions } from "../components/charts/PositionInversions";
import { RiskCards } from "../components/charts/RiskCards";
import { TradeoffChart } from "../components/charts/TradeoffChart";
import { Empty, ErrorState, InsufficientData, Loading } from "../components/common/states";
import { RunHeader } from "../components/run/RunHeader";
import { AdaptationToggle, ScenarioBadge, ScenarioPicker, scenarioKey } from "../components/scenario/ScenarioComponents";
import { ScenarioLauncher } from "../components/scenario/ScenarioLauncher";
import { StrategyCatalog } from "../components/scenario/StrategyCatalog";
import { criteria, rebalance } from "../lib/weights";
import type { Criterion, Weights } from "../lib/weights";
import { RunIdField, ScreenFrame, useSharedQueryParam } from "./ScreenFrame";
import { Icon } from "../components/common/Icon";

const STABILITY_SEED = 1;

function validWeight(value: string, fallback: number): number {
  if (!value.trim()) return fallback;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 1 ? number : fallback;
}

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}

export function RotationLabScreen() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [runId, setRunId] = useSharedQueryParam("runId");
  const scenarioId = params.get("scenarioId") ?? "";
  const adaptation = params.get("adaptation") === "onset_rule" ? "onset_rule" : "none";
  const weights = useMemo<Weights>(() => ({
    water: validWeight(params.get("weight_water") ?? "", 0.25),
    soil: validWeight(params.get("weight_soil") ?? "", 0.25),
    food: validWeight(params.get("weight_food") ?? "", 0.25),
    income: validWeight(params.get("weight_income") ?? "", 0.25),
  }), [params]);
  const debouncedWeights = useDebounced(weights, 350);

  const scenarios = useRunScenarios(runId || null);
  const selectedScenario = scenarios.data?.find((item) => item.scenario_id === scenarioId && item.adaptation_mode === adaptation);
  const baseScenario = scenarios.data?.find((item) => item.scenario_id === "BASE" && item.adaptation_mode === adaptation);
  const summary = useRunSummary(runId || null, selectedScenario?.scenario_id ?? null, adaptation);
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
  const validSum = Math.abs(total - 1) < 0.0001;

  const rankRequest = (scenario: components["schemas"]["ScenarioTag"] | undefined): components["schemas"]["RankRequest"] | null => scenario && validSum
    ? { scenario_id: scenario.scenario_id, adaptation_mode: scenario.adaptation_mode, weights: debouncedWeights, missing_policy: "common_support", stability: { mode: "dirichlet", seed: STABILITY_SEED } }
    : null;
  const ranking = useRank(runId || null, rankRequest(selectedScenario));
  const baseRanking = useRank(runId || null, selectedScenario && selectedScenario.scenario_id !== "BASE" ? rankRequest(baseScenario) : null);

  useEffect(() => {
    if (!scenarioId && scenarios.data?.length) {
      const base = scenarios.data.find((item) => item.scenario_id === "BASE") ?? scenarios.data[0];
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set("scenarioId", base.scenario_id);
        next.set("adaptation", base.adaptation_mode);
        return next;
      }, { replace: true });
    }
  }, [scenarios.data, scenarioId, setParams]);

  const changeWeight = (criterion: Criterion, nextValue: number) => {
    const next = rebalance(weights, criterion, nextValue);
    setParams((current) => {
      const updated = new URLSearchParams(current);
      criteria.forEach((item) => updated.set(`weight_${item}`, next[item].toFixed(2)));
      return updated;
    }, { replace: true });
  };

  const chooseScenario = (key: string) => {
    const scenario = scenarios.data?.find((item) => scenarioKey(item) === key);
    if (!scenario) return;
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set("scenarioId", scenario.scenario_id);
      next.set("adaptation", scenario.adaptation_mode);
      return next;
    }, { replace: true });
  };

  const changeAdaptation = (mode: components["schemas"]["AdaptationMode"]) => {
    const match = scenarios.data?.find((item) => item.scenario_id === selectedScenario?.scenario_id && item.adaptation_mode === mode);
    if (match) chooseScenario(scenarioKey(match));
  };

  const rankData = ranking.data ?? null;
  const usedCriteria = new Set(rankData?.criteria_used ?? []);

  return <ScreenFrame id="rotations">
    <section className="filter-panel" aria-labelledby="rotation-filters">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="filter" /></span><h2 id="rotation-filters">{t("screens.calendar.filters")}</h2></div>
      <div className="filter-grid">
        <RunIdField value={runId} onChange={setRunId} />
        {scenarios.isLoading && <Loading />}
        {scenarios.isError && <ErrorState error={scenarios.error} onRetry={() => void scenarios.refetch()} />}
        {scenarios.data && <ScenarioPicker scenarios={scenarios.data} value={selectedScenario ? scenarioKey(selectedScenario) : ""} onChange={chooseScenario} />}
      </div>
      {selectedScenario && <div className="scenario-layout">
        <ScenarioBadge scenario={selectedScenario} />
        <AdaptationToggle value={selectedScenario.adaptation_mode} onChange={changeAdaptation} disabled={!scenarios.data?.some((item) => item.scenario_id === selectedScenario.scenario_id && item.adaptation_mode !== selectedScenario.adaptation_mode)} />
      </div>}
      {runId && scenarios.data?.length === 0 && <Empty title={t("scenario.noneComputed")} detail={t("scenario.notComputedHint")} />}
      {!runId && <InsufficientData detail={t("ranking.pending")} />}
    </section>

    {runId && <RunHeader runId={runId} />}

    <section className="content-card" aria-labelledby="catalog-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="list" /></span><h2 id="catalog-heading">{t("strategy.catalogTitle")}</h2></div>
      <p className="chart-caption">{t("strategy.dateIsNotRotation")}</p>
      <StrategyCatalog />
    </section>

    <section className="content-card" aria-labelledby="scenario-jobs-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="gear" /></span><h2 id="scenario-jobs-heading">{t("scenario.sectionTitle")}</h2></div>
      <ScenarioLauncher runId={runId} />
    </section>

    <section className="content-card" aria-labelledby="risk-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="risk" /></span><h2 id="risk-heading">{t("screens.rotations.strategies")}</h2></div>
      {summary.isLoading && <Loading />}
      {summary.isError && <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />}
      {summary.data?.items.length ? <RiskCards strategies={summary.data.items} /> : null}
      {summary.data && summary.data.items.length === 0 && <InsufficientData detail={t("common.insufficientData")} />}
    </section>

    <section className="content-card" aria-labelledby="weights-heading">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="sliders" /></span><h2 id="weights-heading">{t("ranking.weights")}</h2></div>
      <div className="weights-grid">{criteria.map((criterion) => {
        const status = !rankData ? null : usedCriteria.has(criterion) ? (rankData.provisional ? "provisional" : "evaluable") : "not_evaluable";
        return <label className="weight-control" key={criterion}>
          <span>{t(`strategy.criteria.${criterion}`)}{status && <span className={`status-chip status-chip--${status}`} data-testid={`criterion-status-${criterion}`}>{t(`ranking.criterionStatuses.${status}`)}</span>}</span>
          <input type="range" min="0" max="1" step="0.01" value={weights[criterion]} data-testid={`weight-${criterion}`} onChange={(event) => changeWeight(criterion, Number(event.currentTarget.value))} aria-valuetext={`${t(`strategy.criteria.${criterion}`)}: ${weights[criterion].toLocaleString(undefined, { style: "percent" })}`} />
          <output>{weights[criterion].toLocaleString(undefined, { style: "percent", maximumFractionDigits: 0 })}</output>
        </label>;
      })}</div>
      <p className={`weight-sum${validSum ? " is-valid" : " is-invalid"}`} role="status">{t("ranking.weightSum")}: {total.toFixed(2)} {validSum ? "✓" : `· ${t("ranking.weightSumError")}`}</p>
      <p className="chart-caption">{t("ranking.autoRebalance")}</p>
      {ranking.isFetching && <p className="chart-caption" role="status">{t("ranking.recalculating")}</p>}
      {ranking.isError && <ErrorState error={ranking.error} onRetry={() => void ranking.refetch()} />}
    </section>

    {!selectedScenario && <Empty title={t("ranking.noRanking")} detail={t("ranking.pending")} />}
    {rankData && <TradeoffChart data={rankData} />}
    {selectedScenario && selectedScenario.scenario_id !== "BASE" && <section className="content-card">
      <PositionInversions base={baseRanking.data} selected={rankData} />
    </section>}
    <p className="chart-caption">{t("common.notBestStrategy")}</p>
  </ScreenFrame>;
}
