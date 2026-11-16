import { useTranslation } from "react-i18next";

import { useStationValidation } from "../../api/queries";
import type { components } from "../../api/types.gen";
import { KindChip } from "./AgronomyKinds";

type Station = components["schemas"]["StationValidationResponse"];

type Metrics = {
  n_comparados?: number;
  rmse_mm_dia?: number | null;
  sesgo_mm_dia?: number | null;
  correlacion_pearson?: number | null;
  periodo?: { desde: string; hasta: string } | null;
  producto_evaluado?: string;
  motivo_sin_correlacion?: string | null;
};

const fmt = (value: number | null | undefined, digits = 2) => (value == null ? "—" : value.toFixed(digits));

/**
 * Evidence-level banner for the satellite rainfall. It always renders the "Level C — pending" text unless the
 * backend reports a real local validation (Level B); a failed request keeps the honest default.
 */
export function StationValidationView({ data }: { data?: Station }) {
  const { t } = useTranslation();
  const levelB = data?.estado_validacion.startsWith("Nivel B") ?? false;
  const metrics = (data?.metricas ?? null) as Metrics | null;

  return <section className={`station-notice station-notice--${levelB ? "b" : "c"}`} aria-labelledby="station-title" data-testid="station-validation" data-level={levelB ? "B" : "C"}>
    <p id="station-title" className="station-notice__level" role="status">{levelB ? t("agronomy.stationLevelB") : t("agronomy.stationLevelC")}</p>
    <p><KindChip kind="satellite" /> {levelB ? data?.mensaje : t("agronomy.stationTextC")}</p>
    {data && !levelB && data.mensaje && <p className="chart-caption" data-testid="station-detail">{data.mensaje}</p>}
    {data?.es_ejemplo_ficticio && <p className="station-notice__example"><KindChip kind="fictitious" /> {t("agronomy.exampleFile")}</p>}
    <p className="chart-caption">{t("agronomy.suggestedSource")}: <strong>{data?.fuente_sugerida ?? "INSIVUMEH - Estación Camotán"}</strong></p>
    {levelB && metrics && <dl className="context-list" data-testid="station-metrics">
      <div><dt>{t("agronomy.product")}</dt><dd>{metrics.producto_evaluado}</dd></div>
      <div><dt>{t("agronomy.nCompared")}</dt><dd>{metrics.n_comparados}</dd></div>
      <div><dt>{t("agronomy.period")}</dt><dd>{metrics.periodo ? `${metrics.periodo.desde} – ${metrics.periodo.hasta}` : "—"}</dd></div>
      <div><dt>{t("agronomy.rmse")}</dt><dd>{fmt(metrics.rmse_mm_dia, 3)}</dd></div>
      <div><dt>{t("agronomy.bias")}</dt><dd>{fmt(metrics.sesgo_mm_dia, 3)}</dd></div>
      <div><dt>{t("agronomy.corr")}</dt><dd>{fmt(metrics.correlacion_pearson, 3)}</dd></div>
    </dl>}
    <div className="station-notice__upload">
      {/* Intentionally disabled: the page does not upload or process files. */}
      <button type="button" className="button button--secondary" disabled aria-disabled="true" aria-describedby="station-upload-note">{t("agronomy.upload")}</button>
      <p id="station-upload-note" className="chart-caption">{t("agronomy.uploadReady")} {t("agronomy.uploadHow")}</p>
    </div>
  </section>;
}

export function StationValidationNotice({ zoneId }: { zoneId: string | null }) {
  const query = useStationValidation(zoneId);
  return <StationValidationView data={query.data} />;
}
