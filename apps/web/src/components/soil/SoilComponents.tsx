import type { ChangeEvent, FormEvent } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useDeclareSoilProperty, useDeleteParcel, useJob, useUploadSoilSamples } from "../../api/queries";
import { useSession } from "../../api/session";
import type { components } from "../../api/types.gen";
import { Empty, ErrorState, InsufficientData, ProvisionalBanner } from "../common/states";
import type { SoilStatusView } from "../../api/adapters";
import { Indicator } from "../indicator/Indicator";

type SoilProperty = SoilStatusView;
type SoilVoi = components["schemas"]["SoilVoiResponse"];

const statusKeys: Record<components["schemas"]["PropertyStatus"], string> = {
  medido: "soil.measured",
  estimado: "soil.estimated",
  declarado: "soil.declared",
  desconocido: "soil.unknown",
  desactualizado: "soil.stale",
  no_representativo: "soil.notRepresentative",
  no_disponible: "soil.notAvailable",
};

export function SoilStatusTable({ properties }: { properties: SoilProperty[] | null }) {
  const { t } = useTranslation();
  if (!properties) return <Empty title={t("soil.noParcel")} />;
  if (properties.length === 0) return <InsufficientData title={t("common.insufficientData")} detail={t("soil.noParcel")} />;

  return <>
  {properties.some((property) => property.value?.provisional || property.age_years?.provisional || property.max_age_years?.provisional || property.depth_cm?.some((depth) => depth.provisional)) && <ProvisionalBanner />}
  <div className="table-scroll"><table className="data-table soil-table" data-testid="soil-table">
    <thead><tr><th>{t("soil.property")}</th><th>{t("soil.status")}</th><th>{t("soil.value")}</th><th>{t("soil.method")}</th><th>{t("soil.depth")}</th><th>{t("soil.sampledAt")}</th><th>{t("soil.representativeness")}</th><th>{t("soil.age")}</th></tr></thead>
    <tbody>{properties.map((property) => <tr key={property.property_code} data-property={property.property_code}>
      <th scope="row">{property.property_code}</th>
      <td>{t(statusKeys[property.status])}</td>
      <td>{property.value ? <Indicator indicator={property.value} compact /> : t("common.notAvailable")}</td>
      <td>{property.method ?? t("common.notAvailable")}</td>
      <td>{property.depth_cm ? <span className="indicator-pair"><Indicator indicator={property.depth_cm[0]} compact /><span aria-hidden="true">–</span><Indicator indicator={property.depth_cm[1]} compact /></span> : t("common.notAvailable")}</td>
      <td>{property.sampled_at ?? t("common.notAvailable")}</td>
      <td>{property.representativeness ?? t("common.notAvailable")}</td>
      <td>{property.age_years ? <Indicator indicator={property.age_years} compact /> : t("common.notAvailable")}</td>
    </tr>)}</tbody>
  </table></div>
  </>;
}

export function SoilUpload({ parcelId }: { parcelId: string }) {
  const { t } = useTranslation();
  const session = useSession();
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadSoilSamples(parcelId || null);
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.currentTarget.files?.[0] ?? null);
    upload.reset();
  };
  const canSend = Boolean(parcelId && file && session);

  return <section className="form-card" aria-labelledby="soil-upload-title">
    <h3 id="soil-upload-title">{t("soil.uploadTitle")}</h3>
    <label className="file-field"><span>{t("soil.chooseCsv")}</span><input type="file" accept=".csv,text/csv" onChange={onChange} /></label>
    {file && <p role="status">{file.name}</p>}
    <button className="button" type="button" disabled={!canSend || upload.isPending} onClick={() => file && upload.mutate(file)}>
      {upload.isPending ? t("common.loading") : t("soil.uploadSend")}
    </button>
    {!session && <p className="chart-caption">{t("soil.signInToUpload")}</p>}
    {!parcelId && <p className="chart-caption">{t("soil.noParcel")}</p>}
    {upload.isError && <ErrorState error={upload.error} />}
    {upload.data && <div role="status" data-testid="upload-result">
      {upload.data.accepted.length > 0 && <p>{t("soil.accepted")}: {upload.data.accepted.map((item) => `${item.property_code} (${item.rows})`).join(", ")}</p>}
      {upload.data.errors.length > 0 && <div className="table-scroll"><table className="data-table" data-testid="row-errors">
        <caption>{t("soil.rowErrors")}</caption>
        <thead><tr><th>{t("soil.row")}</th><th>{t("soil.column")}</th><th>{t("soil.message")}</th></tr></thead>
        <tbody>{upload.data.errors.map((item, index) => <tr key={index}><th scope="row">{item.row}</th><td>{item.column ?? "—"}</td><td>{item.message}</td></tr>)}</tbody>
      </table></div>}
      {upload.data.errors.length === 0 && upload.data.accepted.length === 0 && <InsufficientData detail={t("soil.nothingAccepted")} />}
    </div>}
    <p className="chart-caption">{t("soil.emptyMeansUnknown")}</p>
  </section>;
}

const unitFor: Record<string, string> = { effective_root_depth_cm: "cm", awc_mm_per_m: "mm/m", om_pct: "%" };

export function SoilDeclarationForm({ parcelId }: { parcelId: string }) {
  const { t } = useTranslation();
  const session = useSession();
  const declare = useDeclareSoilProperty(parcelId || null);
  const [property, setProperty] = useState("effective_root_depth_cm");
  const [value, setValue] = useState("");
  const [basis, setBasis] = useState("");
  const valid = Boolean(parcelId && session && value.trim() !== "" && Number.isFinite(Number(value)) && basis.trim().length >= 3);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (valid) declare.mutate({ property, body: { value: Number(value), unit: unitFor[property], basis: basis.trim() } });
  };

  return <form className="form-card" onSubmit={submit} aria-labelledby="soil-declaration-title">
    <h3 id="soil-declaration-title">{t("soil.declareTitle")}</h3>
    <div className="filter-grid">
      <label className="field"><span>{t("soil.propertyLabel")}</span>
        <select value={property} onChange={(event) => setProperty(event.currentTarget.value)}>
          {Object.keys(unitFor).map((code) => <option key={code} value={code}>{code} ({unitFor[code]})</option>)}
        </select>
      </label>
      <label className="field"><span>{t("soil.value")}</span><input type="number" step="any" value={value} onChange={(event) => setValue(event.currentTarget.value)} /></label>
      <label className="field"><span>{t("soil.basis")}</span><input type="text" value={basis} onChange={(event) => setBasis(event.currentTarget.value)} placeholder={t("soil.basisPlaceholder")} /></label>
    </div>
    <button className="button" type="submit" disabled={!valid || declare.isPending}>{declare.isPending ? t("common.loading") : t("soil.declareSend")}</button>
    {!session && <p className="chart-caption">{t("soil.signInToUpload")}</p>}
    <p className="chart-caption">{t("soil.declareHelp")}</p>
    {declare.isError && <ErrorState error={declare.error} />}
    {declare.isSuccess && <p role="status" className="notice">{t("soil.declaredOk")}</p>}
  </form>;
}

export function DeleteParcelControl({ parcelId, onDeleted }: { parcelId: string; onDeleted: () => void }) {
  const { t } = useTranslation();
  const session = useSession();
  const [confirming, setConfirming] = useState(false);
  const remove = useDeleteParcel(parcelId || null);
  const job = useJob(remove.data?.job_id ?? null);
  const done = job.data?.status === "ok";

  useEffect(() => {
    if (done) onDeleted();
  }, [done, onDeleted]);

  if (!session || (!parcelId && !remove.data)) return null;
  return <section className="form-card danger-zone" aria-labelledby="delete-parcel-title">
    <h3 id="delete-parcel-title">{t("privacy.deleteTitle")}</h3>
    <p>{t("privacy.deleteWarning")}</p>
    {!confirming && <button className="button button--danger" type="button" onClick={() => setConfirming(true)}>{t("privacy.deleteStart")}</button>}
    {confirming && !remove.data && <div className="inline-actions">
      <button className="button button--danger" type="button" disabled={remove.isPending} onClick={() => remove.mutate()}>{t("privacy.deleteConfirm")}</button>
      <button className="button button--secondary" type="button" onClick={() => setConfirming(false)}>{t("common.cancel")}</button>
    </div>}
    {remove.isError && <ErrorState error={remove.error} />}
    {remove.data && !done && <p role="status">{t("privacy.deleteRunning")}</p>}
    {done && <p role="status" className="notice">{t("privacy.deleteDone")}</p>}
  </section>;
}

export function VoiPanel({ result, phStatus }: { result: SoilVoi | null; phStatus?: SoilProperty["status"] }) {
  const { t, i18n } = useTranslation();
  if (phStatus === "medido" || result?.applicability === "already_measured") {
    return <InsufficientData title={t("soil.phMeasured")} detail={t("soil.alreadyMeasured")} />;
  }
  if (!result) return <InsufficientData title={t("soil.voiTitle")} detail={t("soil.voiUnavailable")} />;

  return <section className="voi-panel" aria-labelledby="voi-heading">
    <h3 id="voi-heading">{t("soil.voiTitle")}</h3>
    <span className={`status-chip status-chip--${result.property_status}`}>{t(statusKeys[result.property_status])}</span>
    <span className={`status-chip status-chip--${result.applicability}`}>{t(`soil.voiApplicability.${result.applicability}`)}</span>
    {result.outcome && <span className={`status-chip status-chip--${result.outcome}`}>{t(`soil.voiOutcome.${result.outcome}`)}</span>}
    <p>{i18n.language.startsWith("en") ? `${t("soil.rationaleSpanishOnly")} ` : ""}{result.rationale_es}</p>
    {result.outcome === "insufficient_info" && <InsufficientData detail={t("soil.missingMatrix")} />}
    {result.lab_recommended && <p className="notice">{t("soil.labRecommended")}</p>}
    {result.outcome !== "insufficient_info" && !result.lab_recommended && result.outcome && <p className="notice">{t("soil.labNotRecommended")}</p>}
    {result.hypotheticals?.map((hypothetical, index) => <article className="hypothetical-card" key={`${hypothetical.top_strategy_id ?? "scenario"}:${index}`}>
      <span className="hypothetical-label">{t("common.hypothetical")}</span>
      {hypothetical.top_strategy_id && <span className="hypothetical-top">{t("soil.topUnderHypothetical")}: <code>{hypothetical.top_strategy_id}</code></span>}
      {hypothetical.value.provisional && <ProvisionalBanner />}
      <Indicator indicator={hypothetical.value} />
    </article>)}
    {result.range_citation && <p className="chart-caption">{result.range_citation}</p>}
  </section>;
}
