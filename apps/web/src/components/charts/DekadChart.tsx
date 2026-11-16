import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Empty, InsufficientData, ProvisionalBanner } from "../common/states";
import { Indicator } from "../indicator/Indicator";
import { ScenarioBadge } from "../scenario/ScenarioComponents";
import { axisStyle, baseTextStyle, chartColors, legendStyle, valueAxisStyle, chartMotion } from "./chartTheme";

type ChartData = components["schemas"]["DekadChartDTO"];
type ChartMode = "dekad" | "cumulative";

export function DekadChart({ data }: { data: ChartData | null }) {
  const { t } = useTranslation();
  const [chartMode, setChartMode] = useState<ChartMode>("dekad");

  const option = useMemo<EChartsOption>(() => {
    if (!data) return {};
    const labels = data.dekads.map((point) => `${point.start} – ${point.end}`);
    const base: EChartsOption = {
      aria: { enabled: true, decal: { show: true }, description: t("calendar.dekadChartDescription") },
      ...chartMotion(),
      textStyle: baseTextStyle,
      grid: { left: 40, right: 20, top: 44, bottom: 90, containLabel: true },
      tooltip: { show: false },
      xAxis: { type: "category", data: labels, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, rotate: 45 } },
      yAxis: { type: "value", name: "mm", ...valueAxisStyle },
    };

    if (chartMode === "cumulative") {
      return {
        ...base,
        legend: { ...legendStyle, data: [t("calendar.cumulativePef"), t("calendar.cumulativeEtc")] },
        series: [
          { name: t("calendar.cumulativePef"), type: "line", data: data.cumulative.map((point) => point.pef_cum_mm.value), lineStyle: { color: chartColors.water, width: 2.5 }, itemStyle: { color: chartColors.water } },
          { name: t("calendar.cumulativeEtc"), type: "line", data: data.cumulative.map((point) => point.etc_cum_mm.value), lineStyle: { color: chartColors.demand, width: 2.5, type: "dashed" }, itemStyle: { color: chartColors.demand } },
        ],
      };
    }

    const bandAreas = data.stage_bands.flatMap((band) => {
      const overlapping = data.dekads.filter((point) => point.end !== undefined && point.start !== undefined && point.end >= band.start && point.start <= band.end);
      if (overlapping.length === 0) return [];
      const first = overlapping[0];
      const last = overlapping[overlapping.length - 1];
      return [[
        { name: band.stage, xAxis: `${first.start} – ${first.end}`, itemStyle: { color: band.critical ? chartColors.criticalBand : chartColors.neutralBand } },
        { xAxis: `${last.start} – ${last.end}` },
      ]];
    });
    const overPoints = data.dekads.flatMap((point, index) => point.over_threshold && point.exposure_mm?.value != null
      ? [{ name: t("calendar.overThreshold"), coord: [labels[index], point.exposure_mm.value], value: "!" }]
      : []);

    return {
      ...base,
      legend: { ...legendStyle, data: [t("calendar.effectivePrecipitation"), t("calendar.cropDemand"), t("calendar.exposure")] },
      series: [
        { name: t("calendar.effectivePrecipitation"), type: "bar", data: data.dekads.map((point) => point.pef_mm?.value ?? null), itemStyle: { color: chartColors.water, borderRadius: [2, 2, 0, 0] }, markArea: { silent: true, label: { color: "#6f1f19", fontFamily: baseTextStyle.fontFamily, position: "insideTop" }, data: bandAreas as never } },
        { name: t("calendar.cropDemand"), type: "bar", data: data.dekads.map((point) => point.etc_mm?.value ?? null), itemStyle: { color: chartColors.demand, borderRadius: [2, 2, 0, 0] } },
        {
          name: t("calendar.exposure"),
          type: "line",
          data: data.dekads.map((point) => point.exposure_mm?.value ?? null),
          connectNulls: false,
          lineStyle: { color: chartColors.risk, width: 2.5 },
          itemStyle: { color: chartColors.risk },
          symbolSize: 8,
          markPoint: { symbol: "pin", symbolSize: 38, itemStyle: { color: chartColors.risk }, label: { color: "#fff", formatter: "!" }, data: overPoints as never },
        },
      ],
    };
  }, [data, t, chartMode]);

  if (!data) return <Empty title={t("calendar.chartEmpty")} />;
  if (data.dekads.length === 0) return <InsufficientData title={t("calendar.chartEmpty")} />;
  const provisional = data.dekads.some((point) => point.pef_mm?.provisional || point.etc_mm?.provisional || point.exposure_mm?.provisional);
  const overDekads = data.dekads.filter((point) => point.over_threshold);

  return <section className="chart-panel" aria-labelledby="dekad-title" data-testid="dekad-chart">
    <div className="chart-panel__heading"><div><p className="eyebrow">{t("calendar.cohortYear")}: {data.cohort_year} · {t("calendar.cycle")}: {data.cycle_idx} · {t("calendar.plantDate")}: {data.plant_date}</p><h3 id="dekad-title">{t("calendar.dekadChart")}</h3></div>
      <fieldset className="segmented-control">
        <legend>{t("calendar.chartView")}</legend>
        {(["dekad", "cumulative"] as const).map((mode) => <label key={mode}>
          <input type="radio" name="dekad-chart-view" value={mode} checked={chartMode === mode} onChange={() => setChartMode(mode)} />
          <span>{t(`calendar.chartViews.${mode}`)}</span>
        </label>)}
      </fieldset>
    </div>
    <ScenarioBadge scenario={data.scenario} />
    {provisional && <ProvisionalBanner />}
    <div className="chart-canvas" role="img" aria-label={t("calendar.dekadChartDescription")}>
      <ReactECharts option={option} style={{ height: 360, width: "100%" }} notMerge lazyUpdate />
    </div>
    <ul className="stage-list" aria-label={t("calendar.stageBands")}>
      {data.stage_bands.map((band) => <li key={band.stage}><strong>{band.stage}</strong>: {band.start} – {band.end}{band.critical ? ` · ${t("calendar.criticalStage")}` : ""}</li>)}
    </ul>
    {overDekads.length > 0 && <p className="over-threshold-note" data-testid="over-threshold-note">
      {t("calendar.overThresholdList")}: {overDekads.map((point) => `${point.idx} (${point.start} – ${point.end})`).join("; ")}
    </p>}
    <p className="chart-caption">{t("calendar.chartTableValues")}</p>
    <details className="chart-data-details" open>
      <summary>{t("calendar.dekadTable")}</summary>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>{t("calendar.dekadIndex")}</th><th>{t("calendar.date")}</th><th>{t("calendar.effectivePrecipitation")}</th><th>{t("calendar.cropDemand")}</th><th>{t("calendar.exposure")}</th><th>{t("calendar.criticalStage")}</th><th>{t("calendar.overThreshold")}</th></tr></thead>
        <tbody>{data.dekads.map((point) => <tr key={`${point.idx}:${point.start}`} className={point.over_threshold ? "row-over-threshold" : undefined}>
          <th scope="row">{point.idx}</th>
          <td>{point.start} – {point.end}</td>
          <td>{point.pef_mm ? <Indicator indicator={point.pef_mm} compact /> : t("common.notAvailable")}</td>
          <td>{point.etc_mm ? <Indicator indicator={point.etc_mm} compact /> : t("common.notAvailable")}</td>
          <td>{point.exposure_mm ? <Indicator indicator={point.exposure_mm} compact /> : t("common.notAvailable")}</td>
          <td>{point.critical_stage ?? t("common.notAvailable")}</td>
          <td>{point.over_threshold === null || point.over_threshold === undefined ? t("common.notAvailable") : point.over_threshold ? `⚑ ${t("calendar.yes")}` : t("calendar.no")}</td>
        </tr>)}</tbody>
      </table></div>
    </details>
    {data.cumulative.length > 0 && <details className="chart-data-details">
      <summary>{t("calendar.cumulativeTable")}</summary>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>{t("calendar.dekadIndex")}</th><th>{t("calendar.cumulativePef")}</th><th>{t("calendar.cumulativeEtc")}</th></tr></thead>
        <tbody>{data.cumulative.map((point) => <tr key={point.idx}><th scope="row">{point.idx}</th><td><Indicator indicator={point.pef_cum_mm} compact /></td><td><Indicator indicator={point.etc_cum_mm} compact /></td></tr>)}</tbody>
      </table></div>
    </details>}
    {data.etc_system_exploratory && <details><summary>{t("calendar.exploratorySystem")}</summary>
      <p className="chart-caption">{t("calendar.exploratoryNote")}</p>
      <div className="indicator-list">{data.etc_system_exploratory.map((item, index) => item
        ? <Indicator key={`${index}:${item.code}`} indicator={item} />
        : <span key={index}>{t("common.notAvailable")}</span>)}</div>
    </details>}
  </section>;
}
