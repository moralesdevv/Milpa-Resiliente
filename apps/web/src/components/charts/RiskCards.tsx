import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Indicator } from "../indicator/Indicator";
import { ProvisionalBanner } from "../common/states";

type StrategyRisk = components["schemas"]["StrategyRiskDTO"];
type CycleRisk = components["schemas"]["CycleRiskDTO"];
type IndicatorNumber = components["schemas"]["IndicatorNumber"];

function cycleIndicators(cycle: CycleRisk): IndicatorNumber[] {
  return [
    cycle.freq_critical, cycle.severity_median, cycle.severity_p90, cycle.severity_cvar90, cycle.worst_year, cycle.worst_year_severity,
    cycle.coverage.n_valid, cycle.coverage.n_expected, cycle.coverage.n_decided, cycle.coverage.missing_pct,
    cycle.threshold_sensitivity.low, cycle.threshold_sensitivity.central, cycle.threshold_sensitivity.high,
    ...Object.values(cycle.peff_sensitivity),
  ].filter((item): item is IndicatorNumber => Boolean(item));
}

function CycleTable({ strategy }: { strategy: StrategyRisk }) {
  const { t } = useTranslation();
  const methods = [...new Set(strategy.by_cycle.flatMap((cycle) => Object.keys(cycle.peff_sensitivity)))];
  return <div className="table-scroll"><table className="data-table cycle-table" data-testid={`cycle-table-${strategy.strategy_version_id}`}>
    <caption>{t("strategy.byCycle")}</caption>
    <thead><tr>
      <th>{t("calendar.cycle")}</th><th>{t("calendar.variety")}</th>
      <th>{t("strategy.freq")}</th><th>{t("strategy.sevMedian")}</th><th>P90</th><th>CVaR90</th><th>{t("strategy.worstYear")}</th><th>{t("strategy.worstYearSeverity")}</th>
      <th>{t("strategy.nValid")} / {t("strategy.nExpected")}</th>
      <th>{t("strategy.thresholdSensitivity")}</th>
      {methods.map((method) => <th key={method}>Pef · <code>{method}</code></th>)}
    </tr></thead>
    <tbody>{strategy.by_cycle.map((cycle) => <tr key={`${cycle.cycle_idx}:${cycle.variety_id}`}>
      <th scope="row">{cycle.cycle_idx}</th>
      <td><code>{cycle.variety_id}</code></td>
      <td><Indicator indicator={cycle.freq_critical} compact /></td>
      <td><Indicator indicator={cycle.severity_median} compact /></td>
      <td><Indicator indicator={cycle.severity_p90} compact /></td>
      <td><Indicator indicator={cycle.severity_cvar90} compact /></td>
      <td><Indicator indicator={cycle.worst_year} compact /></td>
      <td><Indicator indicator={cycle.worst_year_severity} compact /></td>
      <td>
        {cycle.coverage.n_valid ? <Indicator indicator={cycle.coverage.n_valid} compact /> : t("common.notAvailable")}
        <span aria-hidden="true"> / </span>
        {cycle.coverage.n_expected ? <Indicator indicator={cycle.coverage.n_expected} compact /> : t("common.notAvailable")}
        {cycle.flags.includes("peff_sensible_al_metodo") && <span className="flag-chip" data-testid="peff-flag">{t("strategy.flags.peff_sensible_al_metodo")}</span>}
      </td>
      <td className="cell-stack">{[cycle.threshold_sensitivity.low, cycle.threshold_sensitivity.central, cycle.threshold_sensitivity.high].map((item, index) => item
        ? <Indicator key={index} indicator={item} compact />
        : <span key={index}>{t("common.notAvailable")}</span>)}</td>
      {methods.map((method) => <td key={method}>{cycle.peff_sensitivity[method] ? <Indicator indicator={cycle.peff_sensitivity[method]} compact /> : t("common.notAvailable")}</td>)}
    </tr>)}</tbody>
  </table></div>;
}

export function RiskCards({ strategies }: { strategies: StrategyRisk[] }) {
  const { t } = useTranslation();
  if (strategies.length === 0) return null;

  return <section className="risk-grid" aria-label={t("calendar.riskByStrategy")}>
    {strategies.map((strategy) => <article className="risk-card" key={strategy.strategy_version_id} data-testid="risk-card">
      <div className="risk-card__heading">
        <h3>{strategy.name}</h3>
        <span>{t(`strategy.consistency.${strategy.consistency}`)}</span>
      </div>
      <p className="risk-card__axes">
        {strategy.changes_from_reference.length
          ? `${t("strategy.changesFrom")}: ${strategy.changes_from_reference.map((axis) => t(`strategy.axes.${axis}`)).join(", ")}`
          : t("strategy.isReference")}
        {strategy.overlapping_cohorts && ` · ${t("strategy.overlapping")}`}
      </p>
      <Indicator indicator={strategy.cohort_freq_critical} />
      <CycleTable strategy={strategy} />
      {(strategy.cohort_freq_critical.provisional || strategy.by_cycle.some((cycle) => cycleIndicators(cycle).some((indicator) => indicator.provisional))) && <ProvisionalBanner />}
    </article>)}
  </section>;
}
