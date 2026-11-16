import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { usePlantingOptions, useZonePlantingValidation } from "../../api/queries";
import type { components } from "../../api/types.gen";
import { ErrorState, Loading } from "../common/states";
import { KindChip, KindLegend } from "./AgronomyKinds";

type Result = components["schemas"]["PlantingValidationResponse"];
type Stage = {
  etapa_fao: string;
  duracion_dias: number;
  kc_inicio: number;
  kc_fin: number;
  tipo_dato: string;
  confianza: string;
  supuesto_aplicado: string;
};
type Phenology = { etapas?: Stage[]; ciclo_total_dias?: number | null; nota?: string };
type Limits = { dias_secos_consecutivos_riesgo?: number; lluvia_minima_mm_dia?: number; lluvia_minima_15_dias_mm?: number };

const toNumber = (value: string): number | undefined => (value.trim() === "" ? undefined : Number(value));

export function ProvisionalPlantingNotice() {
  const { t } = useTranslation();
  return <p className="provisional-notice" role="note" data-testid="planting-provisional">{t("agronomy.provisionalNotice")}</p>;
}

export function PlantingResult({ result }: { result: Result }) {
  const { t } = useTranslation();
  const phenology = (result.parametros_fenologicos ?? null) as Phenology | null;
  const stages = phenology?.etapas ?? [];
  const limits = ((result.umbrales_aplicados ?? [])[0] ?? {}) as Limits;
  const warnings = result.advertencias ?? [];
  const assumptions = result.supuestos ?? [];
  const sources = result.fuentes ?? [];
  const total = phenology?.ciclo_total_dias ?? null;

  return <div className="validation-result" role="status" aria-live="polite" data-testid="planting-result">
    {result.fecha_en_ventana === false && <div className="banner banner--warning" data-testid="window-banner">{t("agronomy.windowBanner")}</div>}
    {result.senal_sequia && <div className="banner banner--warning" data-testid="drought-banner">
      <strong>{t("agronomy.droughtBanner")}</strong>
      <p>{t("agronomy.thresholdUsed")}: {t("agronomy.dryThreshold", { days: limits.dias_secos_consecutivos_riesgo, mm: limits.lluvia_minima_mm_dia })}
        {limits.lluvia_minima_15_dias_mm != null && <> · {t("agronomy.rainThreshold", { mm: limits.lluvia_minima_15_dias_mm })}</>}</p>
    </div>}
    <strong>{result.es_valido ? t("agronomy.resultOk") : t("agronomy.resultReview")}</strong>
    <h4>{t("agronomy.alerts")}</h4>
    <ul>{result.alertas.length ? result.alertas.map((alert) => <li key={alert}>{alert}</li>) : <li>{t("agronomy.noAlerts")}</li>}</ul>
    {warnings.length > 0 && <>
      <h4>{t("agronomy.warnings")}</h4>
      <ul data-testid="planting-warnings">{warnings.map((item) => <li key={item}>{item}</li>)}</ul>
    </>}
    <p>{result.recomendacion}</p>
    <dl className="context-list">
      <div><dt>{t("agronomy.validationState")}</dt><dd>{result.estado_validacion} <KindChip kind="assumption" /></dd></div>
      <div><dt>{t("agronomy.waterSource")}</dt><dd>{result.origen_senales_hidricas} <KindChip kind={/declar/i.test(result.origen_senales_hidricas) ? "observed" : "satellite"} /></dd></div>
      <div><dt>{t("calendar.rain15Days")}</dt><dd>{result.precipitacion_15_dias_mm == null ? t("soil.notAvailable") : `${result.precipitacion_15_dias_mm.toFixed(1)} mm`}</dd></div>
      <div><dt>{t("calendar.temperatureOnDate")}</dt><dd>{result.temperatura_media_fecha_c == null ? t("soil.notAvailable") : `${result.temperatura_media_fecha_c.toFixed(1)} °C`}</dd></div>
      <div><dt>{t("calendar.climateCoverage")}</dt><dd>{result.cobertura_climatica.desde} – {result.cobertura_climatica.hasta}</dd></div>
    </dl>
    {stages.length > 0 && <>
      <h4>{t("agronomy.params")} — {result.cultivo}, {result.variedad} <KindChip kind="assumption" /></h4>
      <p>{t("agronomy.kcMid")}: <strong>{result.kc_etapa_media}</strong>{total != null && <> · {t("agronomy.cycleDays")}: <strong>{t("agronomy.days", { n: total })}</strong></>}</p>
      <div className="table-scroll"><table className="data-table" data-testid="phenology-table">
        <thead><tr><th scope="col">{t("agronomy.stage")}</th><th scope="col">{t("agronomy.duration")}</th><th scope="col">{t("agronomy.kc")}</th><th scope="col">{t("agronomy.dataType")}</th><th scope="col">{t("agronomy.confidence")}</th></tr></thead>
        <tbody>{stages.map((row) => <tr key={row.etapa_fao}>
          <th scope="row">{t(`agronomy.stageNames.${row.etapa_fao}`, { defaultValue: row.etapa_fao })}</th>
          <td>{t("agronomy.days", { n: row.duracion_dias })}</td>
          <td>{row.kc_inicio === row.kc_fin ? row.kc_inicio.toFixed(2) : `${row.kc_inicio.toFixed(2)} → ${row.kc_fin.toFixed(2)}`}</td>
          <td>{t(`agronomy.types.${row.tipo_dato}`, { defaultValue: row.tipo_dato })}</td>
          <td>{t(`agronomy.levels.${row.confianza}`, { defaultValue: row.confianza })}</td>
        </tr>)}</tbody>
        <tfoot><tr><th scope="row">{t("agronomy.totalCycle")}</th><td colSpan={4}>{t("agronomy.days", { n: total })}</td></tr></tfoot>
      </table></div>
      <p className="chart-caption">{t("agronomy.kcNote")} {stages[0]?.supuesto_aplicado}</p>
    </>}
    {assumptions.length > 0 && <details className="chart-data-details">
      <summary>{t("agronomy.assumptions")}</summary>
      <ul>{assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
    </details>}
    {sources.length > 0 && <details className="chart-data-details">
      <summary>{t("agronomy.sources")} ({sources.length})</summary>
      <ul data-testid="planting-sources">{sources.map((source) => <li key={String(source.id)}>
        {source.url ? <a href={String(source.url)} target="_blank" rel="noreferrer">{String(source.titulo)}</a> : String(source.titulo)}
        {" "}· {String(source.institucion)}{source.fecha ? ` · ${String(source.fecha)}` : ""}
        {source.nota ? <span className="chart-caption"> {String(source.nota)}</span> : null}
      </li>)}</ul>
    </details>}
    <p className="chart-caption">{result.alcance}</p>
  </div>;
}

export function PlantingValidation({ zoneId, onDate }: { zoneId: string; onDate?: (date: string) => void }) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const options = usePlantingOptions(zoneId);
  const validation = useZonePlantingValidation(zoneId);
  const [crop, setCrop] = useState("maiz");
  const [variety, setVariety] = useState("ICTA B-7");
  const [cycle, setCycle] = useState("");
  const [date, setDate] = useState("2025-05-15");
  const [dryDays, setDryDays] = useState("");
  const [rain15, setRain15] = useState("");

  const crops = options.data?.cultivos ?? [];
  const current = crops.find((item) => item.clave === crop) ?? crops[0];
  const varieties = current?.variedades ?? [];
  const lang = i18n.language.startsWith("es") ? "es" : "en";

  const changeCrop = (key: string) => {
    setCrop(key);
    const next = crops.find((item) => item.clave === key);
    if (next?.variedades[0]) setVariety(next.variedades[0].nombre);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onDate?.(date);
    validation.mutate({
      cultivo: crop,
      variedad: variety,
      fecha_siembra: date,
      ciclo: cycle || undefined,
      dias_secos_recientes: toNumber(dryDays),
      lluvia_15_dias_mm: toNumber(rain15),
      idioma: lang,
    });
  };

  return <div className="planting-validation">
    <h3>{t("agronomy.formTitle")}</h3>
    <p>{t("agronomy.formScope")}</p>
    <ProvisionalPlantingNotice />
    <KindLegend />
    {options.isLoading && <Loading />}
    {options.isError && <p className="banner banner--warning" role="alert">{t("agronomy.optionsError")}</p>}
    {options.data && <form className="form-grid" onSubmit={submit}>
      <label htmlFor="planting-crop">{t("agronomy.crop")}</label>
      <select id="planting-crop" value={current?.clave ?? crop} onChange={(event) => changeCrop(event.target.value)}>
        {crops.map((item) => <option key={item.clave} value={item.clave}>{item.nombre}</option>)}
      </select>
      <label htmlFor="planting-variety">{t("agronomy.variety")}</label>
      <select id="planting-variety" value={variety} onChange={(event) => setVariety(event.target.value)}>
        {varieties.map((item) => <option key={item.nombre} value={item.nombre}>{item.nombre}</option>)}
      </select>
      <label htmlFor="planting-cycle">{t("agronomy.cycle")}</label>
      <select id="planting-cycle" value={cycle} onChange={(event) => setCycle(event.target.value)}>
        <option value="">{t("agronomy.cycleAuto")}</option>
        {options.data.ciclos.map((item) => <option key={item.ciclo} value={item.ciclo}>{item.ciclo} ({item.inicio} → {item.fin})</option>)}
      </select>
      <label htmlFor="planting-date">{t("agronomy.plantingDate")}</label>
      <input id="planting-date" type="date" required value={date} onChange={(event) => setDate(event.target.value)} />
      <label htmlFor="planting-dry">{t("agronomy.dryDays")}</label>
      <input id="planting-dry" type="number" min={0} max={366} step={1} inputMode="numeric" value={dryDays} onChange={(event) => setDryDays(event.target.value)} />
      <label htmlFor="planting-rain">{t("agronomy.rain15")}</label>
      <input id="planting-rain" type="number" min={0} max={2000} step={0.1} inputMode="decimal" value={rain15} onChange={(event) => setRain15(event.target.value)} />
      <p className="chart-caption">{t("agronomy.waterHelp")}</p>
      <button className="button" type="submit" disabled={validation.isPending}>
        {validation.isPending ? t("agronomy.validating") : t("agronomy.validate")}
      </button>
    </form>}
    {validation.isError && <ErrorState error={validation.error} onRetry={() => validation.reset()} />}
    {validation.data && <PlantingResult result={validation.data} />}
    <p><Link className="button button--secondary" to={{ pathname: "/rotations", search: location.search }}>{t("agronomy.continue")}</Link></p>
  </div>;
}
