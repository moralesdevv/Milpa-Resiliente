import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useRainyOnset } from "../../api/queries";
import type { components } from "../../api/types.gen";
import { ErrorState, Loading } from "../common/states";
import { KindChip } from "./AgronomyKinds";

type Onset = components["schemas"]["RainySeasonOnsetResponse"];

const YEARS = Array.from({ length: 25 }, (_, index) => 2025 - index);
const SEARCH_START = "04-01";
const SEARCH_END = "07-31";

type Criterion = { acumulado_minimo_mm?: number; continuidad_minima_mm?: number };

/** Always visible, also while loading or when the request fails. */
export function SandboxBanner() {
  const { t } = useTranslation();
  return <div className="sandbox-banner" role="note" data-testid="sandbox-banner">
    <strong>{t("agronomy.sandboxBanner")}</strong>
    <p>{t("agronomy.sandboxText")}</p>
  </div>;
}

export function RainyOnsetView({ data }: { data: Onset }) {
  const { t } = useTranslation();
  const criterion = data.criterio as Criterion;
  const evaluated = data.precipitacion_pentadas.filter((p) => p.inicio.slice(5) >= SEARCH_START && p.inicio.slice(5) <= SEARCH_END);
  const entradas = data.entradas as { dias_con_dato?: number; primer_dia?: string | null; ultimo_dia?: string | null };
  const delay = data.retraso_adaptacion;
  const outcome = data.fecha_estimada_inicio
    ? data.fecha_estimada_inicio
    : data.resultado === "datos_insuficientes" ? t("agronomy.insufficientData") : t("agronomy.notDetected");

  return <div className="onset" data-testid="rainy-onset">
    <p className="onset__kinds"><KindChip kind="simulation" /> <KindChip kind="satellite" /> <KindChip kind="assumption" /></p>
    <dl className="context-list">
      <div><dt>{t("agronomy.estimatedDate")}</dt><dd className="onset__date" data-testid="onset-date">{outcome}</dd></div>
      <div><dt>{t("agronomy.state")}</dt><dd>{data.estado}</dd></div>
      <div><dt>{t("agronomy.method")}</dt><dd>{data.metodo}</dd></div>
      <div><dt>{t("agronomy.criterion")}</dt><dd>{t("agronomy.criterionText", { mm: criterion.acumulado_minimo_mm, cont: criterion.continuidad_minima_mm })}</dd></div>
      <div><dt>{t("agronomy.precipSource")}</dt><dd>{data.fuente_precipitacion}</dd></div>
      <div><dt>{t("agronomy.inputData")}</dt><dd>{t("agronomy.daysWithData")}: {entradas.dias_con_dato ?? "—"}{entradas.primer_dia ? ` (${entradas.primer_dia} – ${entradas.ultimo_dia})` : ""}</dd></div>
    </dl>
    <p className="chart-caption">{t("agronomy.criterionSource")}</p>
    {delay && <div className={`onset__delay${delay.advertencias.length ? " onset__delay--warn" : ""}`} data-testid="onset-delay">
      <h4>{t("agronomy.delay")}</h4>
      {delay.dias_diferencia != null && <p>{t("agronomy.delayDays", { n: delay.dias_diferencia })}</p>}
      {delay.advertencias.map((item) => <p key={item} role="status">{item}</p>)}
      <p className="chart-caption">{delay.nota}</p>
    </div>}
    <details className="chart-data-details">
      <summary>{t("agronomy.pentads")}</summary>
      <div className="table-scroll"><table className="data-table" data-testid="pentad-table">
        <thead><tr><th scope="col">{t("agronomy.pentad")}</th><th scope="col">{t("agronomy.period")}</th><th scope="col">{t("agronomy.rainMm")}</th><th scope="col">{t("agronomy.complete")}</th></tr></thead>
        <tbody>{evaluated.map((p) => <tr key={p.pentada} className={p.inicio === data.fecha_estimada_inicio ? "row-over-threshold" : undefined}>
          <th scope="row">{p.pentada}{p.inicio === data.fecha_estimada_inicio ? ` · ${t("agronomy.startPentad")}` : ""}</th>
          <td>{p.inicio} – {p.fin}</td>
          <td>{p.precipitacion_mm == null ? t("agronomy.noData") : p.precipitacion_mm.toFixed(1)}</td>
          <td>{p.completa ? t("agronomy.yes") : t("agronomy.no")}</td>
        </tr>)}</tbody>
      </table></div>
    </details>
    <h4>{t("agronomy.limitations")}</h4>
    <ul className="limitation-list" data-testid="onset-limitations">{data.limitaciones.map((item) => <li key={item}>{item}</li>)}</ul>
  </div>;
}

export function RainyOnsetSandbox({ zoneId, plantingDate }: { zoneId: string | null; plantingDate: string | null }) {
  const { t } = useTranslation();
  const [year, setYear] = useState(2025);
  const onset = useRainyOnset(zoneId, year, plantingDate);
  return <section className="onset-section" aria-labelledby="onset-title">
    <h3 id="onset-title">{t("agronomy.onsetTitle")}</h3>
    <SandboxBanner />
    <label className="field"><span>{t("agronomy.year")}</span>
      <select value={year} onChange={(event) => setYear(Number(event.currentTarget.value))}>
        {YEARS.map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
    {onset.isLoading && <Loading />}
    {onset.isError && <ErrorState error={onset.error} onRetry={() => void onset.refetch()} />}
    {onset.data && <RainyOnsetView data={onset.data} />}
  </section>;
}
