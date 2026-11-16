import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Indicator, ProvenancePanel } from "../indicator/Indicator";
import { Empty, InsufficientData, ProvisionalBanner } from "../common/states";
import { ScenarioBadge } from "../scenario/ScenarioComponents";

type HeatmapData = components["schemas"]["HeatmapDTO"];
type CellState = components["schemas"]["CellState"];

const states: CellState[] = ["critical", "non_critical", "insufficient_data", "not_evaluable"];
const stateMarks: Record<CellState, string> = { critical: "▲", non_critical: "●", insufficient_data: "?", not_evaluable: "—" };

export function Heatmap({ data }: { data: HeatmapData | null }) {
  const { t } = useTranslation();
  if (!data) return <Empty title={t("calendar.heatmapEmpty")} detail={t("calendar.selectFilters")} />;
  if (data.plant_md.length === 0 || data.years.length === 0) {
    return <InsufficientData title={t("calendar.heatmapEmpty")} detail={t("calendar.heatmapInsufficient")} />;
  }
  const consistentWindow = data.consistent_window;
  const inWindow = (date: string) => Boolean(consistentWindow && date >= consistentWindow.start_md && date <= consistentWindow.end_md);

  return <section className="chart-panel" aria-labelledby="heatmap-heading" data-testid="heatmap">
    <div className="chart-panel__heading">
      <div><p className="eyebrow">{t("calendar.heatmapEyebrow")}</p><h3 id="heatmap-heading">{t(`calendar.views.${data.view}`)}</h3></div>
      <span className="mode-chip">{t(`mode.${data.label}`)}</span>
    </div>
    <ScenarioBadge scenario={data.scenario} />
    {[
      ...data.pct_critical_by_date,
      ...data.n_decided_by_date,
      ...data.severity.flat(),
    ].some((indicator) => indicator?.provisional) && <ProvisionalBanner />}
    <div className="heatmap-legend" aria-label={t("calendar.heatmapLegend")} data-testid="heatmap-legend">
      {states.map((state) => <span className={`heatmap-legend__item heatmap-state--${state}`} key={state}>
        <i aria-hidden="true">{stateMarks[state]}</i>{t(`calendar.cellStates.${state}`)}
      </span>)}
      {consistentWindow && <span className="heatmap-legend__item heatmap-legend__window"><i aria-hidden="true">▮</i>{t("calendar.consistentWindow")}: {consistentWindow.start_md} – {consistentWindow.end_md}</span>}
    </div>
    <div className="heatmap-scroll" role="region" tabIndex={0} aria-label={t("calendar.heatmapTableDescription")}>
      <table className="heatmap-table">
        <thead><tr><th>{t("calendar.cohortYear")}</th>{data.plant_md.map((date) => <th scope="col" key={date} className={inWindow(date) ? "is-consistent-window" : undefined}>{date}{inWindow(date) && <span className="visually-hidden"> ({t("calendar.consistentWindow")})</span>}</th>)}</tr></thead>
        <tbody>{data.years.map((year, yearIndex) => <tr key={year}>
          <th scope="row">{year}</th>
          {data.plant_md.map((date, dateIndex) => {
            const state = data.state[yearIndex]?.[dateIndex] ?? "not_evaluable";
            const severity = data.severity[yearIndex]?.[dateIndex];
            return <td key={`${year}:${date}`} className={`heatmap-state heatmap-state--${state}${inWindow(date) ? " is-consistent-window" : ""}`} data-state={state}>
              <span><b aria-hidden="true">{stateMarks[state]} </b>{t(`calendar.cellStates.${state}`)}</span>
              {severity && <details className="heatmap-cell-detail">
                <summary>{t("calendar.severity")}</summary>
                <Indicator indicator={severity} />
              </details>}
            </td>;
          })}
        </tr>)}</tbody>
        <tfoot><tr>
          <th scope="row">{t("calendar.criticalShare")}</th>
          {data.plant_md.map((date, index) => <td key={date} className={inWindow(date) ? "is-consistent-window" : undefined}>
            {data.pct_critical_by_date[index] ? <Indicator indicator={data.pct_critical_by_date[index]} compact /> : t("common.notAvailable")}
            {data.n_decided_by_date[index] && <div className="heatmap-footnote">
              <span>{t("calendar.decidedCount")}</span><Indicator indicator={data.n_decided_by_date[index]} compact />
            </div>}
          </td>)}
        </tr></tfoot>
      </table>
    </div>
    {data.aggregation_rule && <p className="chart-caption" data-testid="aggregation-rule">{t("calendar.aggregationRule")}: {data.aggregation_rule}</p>}
    <ProvenancePanel provenance={data.provenance} />
    {data.thresholds_used.length > 0 ? <details className="chart-data-details" open>
      <summary>{t("calendar.thresholdsUsed")}</summary>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>{t("calendar.stage")}</th><th>{t("calendar.thresholdValue")}</th><th>{t("calendar.peffMethod")}</th><th>{t("provenance.citation")}</th><th>{t("calendar.thresholdStatus")}</th></tr></thead>
        <tbody>{data.thresholds_used.map((item) => <tr key={`${item.stage}:${item.peff_method}`}>
          <th scope="row">{item.stage}</th>
          <td>{item.value} {item.unit}</td>
          <td><code>{item.peff_method}</code></td>
          <td>{item.citation ?? t("calendar.noCitation")}</td>
          <td>{item.provisional ? t("common.provisionalShort") : t("calendar.cited")}</td>
        </tr>)}</tbody>
      </table></div>
    </details> : <p className="chart-caption" data-testid="heatmap-no-thresholds">{t("calendar.noThresholds")}</p>}
  </section>;
}
