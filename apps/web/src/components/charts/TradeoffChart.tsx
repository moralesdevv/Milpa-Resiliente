import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Empty, InsufficientData, ProvisionalBanner } from "../common/states";
import { Indicator } from "../indicator/Indicator";
import { StabilityMeter } from "./StabilityMeter";
import { axisStyle, baseTextStyle, chartColors, legendStyle, valueAxisStyle, chartMotion } from "./chartTheme";

type RankData = components["schemas"]["RankResponse"];
type Criterion = components["schemas"]["Criterion"];

const allCriteria: Criterion[] = ["water", "soil", "food", "income"];

export function TradeoffChart({ data }: { data: RankData | null }) {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");

  const option = useMemo<EChartsOption>(() => {
    if (!data || data.ranking.length === 0) return {};
    const used = data.criteria_used;
    return {
      aria: { enabled: true, decal: { show: true }, description: t("ranking.tradeoffDescription") },
      ...chartMotion(),
      textStyle: baseTextStyle,
      color: [...chartColors.series],
      grid: { left: 30, right: 20, top: 50, bottom: 40, containLabel: true },
      legend: { ...legendStyle, data: data.ranking.map((row) => row.name) },
      tooltip: { show: false },
      xAxis: { type: "category", data: used.map((criterion) => t(`strategy.criteria.${criterion}`)), ...axisStyle },
      yAxis: { type: "value", min: 0, max: 1, ...valueAxisStyle },
      series: data.ranking.map((row) => ({
        name: row.name,
        type: "bar" as const,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        data: used.map((criterion) => row.criteria?.[criterion]?.normalised?.value ?? null),
      })),
    };
  }, [data, t]);

  if (!data) return <Empty title={t("ranking.noRanking")} detail={t("ranking.pending")} />;

  const used = new Set(data.criteria_used);
  const excluded = allCriteria.filter((criterion) => !used.has(criterion));
  const hasProvisional = data.provisional
    || data.weight_coverage?.provisional
    || data.top_margin?.provisional
    || data.ranking.some((row) => row.total.provisional
      || row.rank.provisional
      || Object.values(row.criteria ?? {}).some((cell) => cell.indicator?.provisional || cell.normalised?.provisional));

  return <section className="chart-panel" aria-labelledby="tradeoff-title" data-testid="ranking-panel" data-status={data.status}>
    <div className="chart-panel__heading"><div><p className="eyebrow">{t("ranking.supportCommon")}</p><h3 id="tradeoff-title">{t("ranking.resultTitle")}</h3></div>
      <span className={`status-chip status-chip--${data.status}`}>{t(`ranking.rankingStatus.${data.status}`)}</span>
    </div>
    {hasProvisional && <ProvisionalBanner />}
    <div className="ranking-summary">
      {data.weight_coverage && <Indicator indicator={data.weight_coverage} />}
      {data.top_margin && <Indicator indicator={data.top_margin} />}
    </div>
    {data.margin_within_uncertainty && <p className="notice" data-testid="margin-note">{t("ranking.marginWithinUncertainty")}</p>}
    {excluded.length > 0 && <div className="excluded-criteria" data-testid="excluded-criteria">
      <h4>{t("ranking.excludedCriteria")}</h4>
      <ul>{excluded.map((criterion) => <li key={criterion}><strong>{t(`strategy.criteria.${criterion}`)}</strong>: {t("ranking.excludedReason")}</li>)}</ul>
    </div>}

    {data.status === "insufficient" && <>
      <InsufficientData title={t("ranking.rankingStatus.insufficient")} detail={t("ranking.insufficientExplain")} />
      {data.partial_table && data.partial_table.length > 0 && <div className="table-scroll"><table className="data-table" data-testid="partial-table">
        <caption>{t("ranking.partialTable")}</caption>
        <thead><tr><th>{t("forms.strategyId")}</th>{[...used].map((criterion) => <th key={criterion}>{t(`strategy.criteria.${criterion}`)}</th>)}</tr></thead>
        <tbody>{data.partial_table.map((row) => <tr key={row.strategy_version_id}>
          <th scope="row">{row.name}</th>
          {[...used].map((criterion) => <td key={criterion}>{row.values[criterion] ? <Indicator indicator={row.values[criterion]} compact /> : t("common.notAvailable")}</td>)}
        </tr>)}</tbody>
      </table></div>}
    </>}

    {data.ranking.length > 0 && <>
      <div className="chart-canvas" role="img" aria-label={t("ranking.tradeoffDescription")}>
        <ReactECharts option={option} style={{ height: 300, width: "100%" }} notMerge lazyUpdate />
      </div>
      <div className="table-scroll"><table className="data-table ranking-table" data-testid="ranking-table">
        <thead><tr><th>{t("ranking.rank")}</th><th>{t("forms.strategyId")}</th><th>{t("ranking.score")}</th><th>{t("ranking.criterion")}</th></tr></thead>
        <tbody>{data.ranking.map((row) => <tr key={row.strategy_version_id} data-strategy={row.strategy_version_id}>
          <td><Indicator indicator={row.rank} compact /></td>
          <th scope="row">{row.name}</th>
          <td><Indicator indicator={row.total} compact /></td>
          <td>{Object.entries(row.criteria ?? {}).map(([criterion, cell]) => <div className="criterion-cell" key={criterion}>
            <strong>{t(`strategy.criteria.${criterion}`, criterion)}</strong>
            {cell.status && <span className={`status-chip status-chip--${cell.status}`}>{t(`ranking.criterionStatuses.${cell.status}`)}</span>}
            {cell.normalised && <Indicator indicator={cell.normalised} compact />}
          </div>)}</td>
        </tr>)}</tbody>
      </table></div>
    </>}

    <StabilityMeter stability={data.stability} />

    <details open><summary>{t("ranking.decisionLog")}</summary>
      {data.decision_log.length ? <ul className="explanation-list" data-testid="decision-log">{data.decision_log.map((item, index) => <li key={index}>
        {item.criterion && <code>{item.criterion}</code>} {english && item.message_en ? item.message_en : item.message_es}
      </li>)}</ul> : <p className="chart-caption">{t("ranking.noDecisions")}</p>}
    </details>
    <details open><summary>{t("ranking.explanations")}</summary>
      {data.explanations.length ? <ul className="explanation-list" data-testid="pair-explanations">{data.explanations.map((item, index) => <li key={index}>
        {english && item.text_en ? item.text_en : item.text_es}
      </li>)}</ul> : <p className="chart-caption">{t("ranking.noExplanations")}</p>}
    </details>
    <p className="chart-caption">{t("common.stabilityInterpretation")}</p>
  </section>;
}
