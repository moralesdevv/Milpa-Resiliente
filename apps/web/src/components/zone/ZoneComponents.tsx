import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";

import { en } from "../../api/engine-text";
import type { QualityView, ZoneContextView } from "../../api/adapters";
import type { components } from "../../api/types.gen";
import { Empty, InsufficientData, Loading, ProvisionalBanner } from "../common/states";
import { Indicator } from "../indicator/Indicator";

const ZoneMap = lazy(() => import("./ZoneMap"));

type Context = ZoneContextView;
type Quality = QualityView;
type Parcel = components["schemas"]["ParcelOut"];

export function ZoneContextBlock({ context, parcel }: { context: Context | undefined; parcel?: Parcel | null }) {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  if (!context) return <InsufficientData detail={t("zone.noContext")} />;
  const cells = context.cells ?? [];
  const crops = context.crops ?? [];

  return <>
    {context.synthetic_fixture && <ProvisionalBanner>{t("run.syntheticFixture")}</ProvisionalBanner>}
    {context.state === "insufficient_data" && <InsufficientData detail={context.message} />}
    {cells.length > 0 && <>
      <Suspense fallback={<Loading />}><ZoneMap cells={cells} parcel={parcel} area={context.area} /></Suspense>
      <div className="table-scroll"><table className="data-table">
        <caption>{t("zone.cells")}</caption>
        <thead><tr><th>{t("zone.cell")}</th><th>{t("zone.cellSource")}</th><th>{t("zone.cellWeight")}</th></tr></thead>
        <tbody>{cells.map((cell) => <tr key={cell.cell_id}>
          <th scope="row">#{cell.cell_id}</th><td>{cell.source}</td><td><Indicator indicator={cell.weight} compact /></td>
        </tr>)}</tbody>
      </table></div>
    </>}
    {crops.length > 0 ? <ul className="crop-list" aria-label={t("zone.crops")}>
      {crops.map((crop) => <li key={crop.code}>
        <strong>{english ? crop.name_en : crop.name_es}</strong>
        <span>{t("zone.seasons")}: {crop.seasons.join(", ")}</span>
        {!crop.calendar_validated && <span className="pending-mark" data-testid="pending-mark">[{t("zone.pendingValidation")}]</span>}
      </li>)}
    </ul> : context.state !== "insufficient_data" && <Empty title={t("zone.noCrops")} />}
    {context.pending && context.pending.length > 0 && <div className="pending-list">
      <h4>{t("zone.pendingDecisions")}</h4>
      <ul>{context.pending.map((item) => <li key={item}><span className="pending-mark">[{t("zone.pendingValidation")}]</span> {item}</li>)}</ul>
    </div>}
  </>;
}

const formatPct = (value: number) => `${new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value)} %`;

export function DataQualityBlock({ quality, sources }: { quality: Quality; sources: components["schemas"]["SourceOut"][] | undefined }) {
  const { t } = useTranslation();
  const rows = quality.coverage ?? [];
  const comparisons = quality.comparisons ?? [];
  const variables = [...new Set(rows.map((row) => row.variable))];
  const years = [...new Set(rows.map((row) => row.year))].sort((a, b) => a - b);
  const sourceList = sources?.length ? sources : quality.sources ?? [];

  return <>
    {quality.state === "insufficient_data" && <InsufficientData detail={String(quality.message ?? t("common.insufficientData"))} />}
    {sourceList.length > 0 && <div className="table-scroll"><table className="data-table" data-testid="sources-table">
      <caption>{t("quality.sources")}</caption>
      <thead><tr><th>{t("quality.product")}</th><th>{t("quality.institution")}</th><th>{t("provenance.version")}</th><th>{t("quality.origin")}</th></tr></thead>
      <tbody>{sourceList.map((source) => <tr key={source.code}>
        <th scope="row">{en(source.product_name)}</th><td>{en(source.institution)}</td>
        <td>{source.version ?? t("common.notAvailable")}</td>
        <td>{source.is_nasa ? t("quality.nasa") : t("quality.notNasa")}</td>
      </tr>)}</tbody>
    </table></div>}
    {rows.length > 0 && <div className="table-scroll"><table className="data-table" data-testid="coverage-table">
      <caption>{t("quality.coverage")}</caption>
      <thead><tr><th>{t("quality.variable")}</th>{years.map((year) => <th key={year} scope="col">{year}</th>)}</tr></thead>
      <tbody>{variables.map((variable) => <tr key={variable}>
        <th scope="row">{variable}</th>
        {years.map((year) => {
          const cell = rows.find((row) => row.variable === variable && row.year === year);
          const pct = cell?.missing_pct.value;
          if (pct == null) return <td key={year} className="coverage-cell coverage-cell--none">{t("common.notAvailable")}</td>;
          const level = pct === 0 ? "ok" : pct < 10 ? "some" : "partial";
          return <td key={year} className={`coverage-cell coverage-cell--${level}`} title={t("quality.coverageCell", { variable, year, pct: formatPct(pct) })}>
            <span className="visually-hidden">{t("quality.coverageCell", { variable, year, pct: formatPct(pct) })}</span>
            <span aria-hidden="true">{formatPct(pct)}{level === "partial" ? " ◐" : ""}</span>
          </td>;
        })}
      </tr>)}</tbody>
    </table>
    <p className="chart-caption">{t("quality.coverageNote")}</p></div>}
    {comparisons.length > 0 && <div className="table-scroll"><table className="data-table">
      <caption>{t("quality.comparisons")}</caption>
      <thead><tr><th>{t("quality.pair")}</th><th>{t("quality.bias")}</th><th>{t("quality.correlation")}</th></tr></thead>
      <tbody>{comparisons.map((item) => <tr key={item.pair}>
        <th scope="row">{item.pair}</th><td><Indicator indicator={item.bias} compact /></td><td><Indicator indicator={item.correlation} compact /></td>
      </tr>)}</tbody>
    </table></div>}
    {quality.ea_sensitivity && <Indicator indicator={quality.ea_sensitivity} />}
    {quality.limitations.length > 0 && <div className="limitation-block"><h4>{t("quality.limitations")}</h4><ul className="limitation-list" data-testid="data-limitations">{quality.limitations.map((item) => <li key={item}>{en(item)}</li>)}</ul></div>}
  </>;
}
