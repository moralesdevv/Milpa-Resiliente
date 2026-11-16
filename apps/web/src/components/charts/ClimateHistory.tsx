import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { InsufficientData, ProvisionalBanner } from "../common/states";
import { Indicator, ProvenancePanel } from "../indicator/Indicator";
import { axisStyle, baseTextStyle, chartColors, legendStyle, valueAxisStyle, chartMotion } from "./chartTheme";

type History = components["schemas"]["ClimateHistoryDTO"];

export function ClimateHistory({ history }: { history: History }) {
  const { t } = useTranslation();
  const years = useMemo(() => history.years ?? [], [history.years]);
  const trends = history.trends ?? [];

  const option = useMemo<EChartsOption>(() => ({
    aria: { enabled: true, decal: { show: true }, description: t("calendar.historyChartDescription") },
    ...chartMotion(),
    textStyle: baseTextStyle,
    grid: { left: 40, right: 20, top: 44, bottom: 50, containLabel: true },
    legend: { ...legendStyle, data: [t("calendar.annualPrecipitation"), t("calendar.annualEt0")] },
    tooltip: { show: false },
    xAxis: { type: "category", data: years.map((item) => item.year), ...axisStyle },
    yAxis: { type: "value", name: "mm", ...valueAxisStyle },
    series: [
      { name: t("calendar.annualPrecipitation"), type: "bar", barMaxWidth: 26, data: years.map((item) => item.precip_mm.value), itemStyle: { color: chartColors.water, borderRadius: [2, 2, 0, 0] } },
      { name: t("calendar.annualEt0"), type: "line", data: years.map((item) => item.et0_mm.value), lineStyle: { color: chartColors.demand, width: 2.5 }, itemStyle: { color: chartColors.demand }, symbolSize: 6 },
    ],
  }), [years, t]);

  if (years.length === 0) {
    return <InsufficientData detail={history.message ?? t("calendar.historyEmpty")} />;
  }
  const provisional = years.some((item) => item.precip_mm.provisional || item.et0_mm.provisional);

  return <div data-testid="climate-history">
    {provisional && <ProvisionalBanner />}
    <div className="chart-canvas" role="img" aria-label={t("calendar.historyChartDescription")}>
      <ReactECharts option={option} style={{ height: 300, width: "100%" }} notMerge lazyUpdate />
    </div>
    {trends.length > 0 && <ul className="trend-list" aria-label={t("calendar.trends")}>
      {trends.map((trend) => <li key={trend.variable}><Indicator indicator={trend.change_per_decade} /><p className="chart-caption">{trend.description_es}</p></li>)}
    </ul>}
    <details className="chart-data-details">
      <summary>{t("calendar.historyTable")}</summary>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>{t("calendar.year")}</th><th>{t("calendar.annualPrecipitation")}</th><th>{t("calendar.annualEt0")}</th><th>{t("calendar.validDays")}</th></tr></thead>
        <tbody>{years.map((item) => <tr key={item.year}>
          <th scope="row">{item.year}</th>
          <td><Indicator indicator={item.precip_mm} compact /></td>
          <td><Indicator indicator={item.et0_mm} compact /></td>
          <td><Indicator indicator={item.n_valid_days} compact /></td>
        </tr>)}</tbody>
      </table></div>
    </details>
    {history.provenance && <ProvenancePanel provenance={history.provenance} />}
  </div>;
}
