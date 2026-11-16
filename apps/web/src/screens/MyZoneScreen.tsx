import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { useSession } from "../api/session";
import { useJocotanSoilGrids, useParcel, useParcelSoil, useSoilVoi, useZone, useZoneDataQuality, useZones } from "../api/queries";
import { Empty, ErrorState, InsufficientData, Loading, ProvisionalBanner } from "../components/common/states";
import { Indicator } from "../components/indicator/Indicator";
import { DeleteParcelControl, SoilDeclarationForm, SoilStatusTable, SoilUpload, VoiPanel } from "../components/soil/SoilComponents";
import { DataQualityBlock, ZoneContextBlock } from "../components/zone/ZoneComponents";
import { SourceStatus } from "../components/zone/SourceStatus";
import { PlantingValidation } from "../components/zone/PlantingValidation";
import { RainyOnsetSandbox } from "../components/zone/RainyOnsetSandbox";
import { StationValidationNotice } from "../components/zone/StationValidationNotice";
import { QueryField, RunIdField, ScreenFrame, useSharedQueryParam } from "./ScreenFrame";
import { Icon } from "../components/common/Icon";

export function MyZoneScreen() {
  const { t, i18n } = useTranslation();
  const session = useSession();
  const demo = Boolean(session?.demo);
  const [params, setParams] = useSearchParams();
  const zoneId = params.get("zoneId") ?? "";
  const [parcelId, setParcelId] = useSharedQueryParam("parcelId");
  const [runId, setRunId] = useSharedQueryParam("runId");
  const [plantingDate, setPlantingDate] = useState<string | null>(null);
  const zones = useZones();
  const zone = useZone(zoneId || null);
  const soilGrids = useJocotanSoilGrids(Boolean(zone.data && /jocotan|camotan/i.test(zone.data.name)));
  const quality = useZoneDataQuality(zoneId || null);
  const parcel = useParcel(parcelId || null);
  const soil = useParcelSoil(parcelId || null);
  const soilVoi = useSoilVoi(runId || null);
  const ph = soil.data?.find((property) => property.property_code.toLowerCase() === "ph");
  const clearParcel = useCallback(() => setParcelId(""), [setParcelId]);

  const changeZone = (nextZone: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (nextZone) next.set("zoneId", nextZone);
      else next.delete("zoneId");
      next.delete("parcelId");
      return next;
    }, { replace: true });
  };

  // One pilot zone is the common case: select it automatically so the screen shows data on arrival.
  const firstZoneId = zones.data?.[0]?.zone_id;
  useEffect(() => {
    if (!zoneId && firstZoneId) {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set("zoneId", firstZoneId);
        return next;
      }, { replace: true });
    }
  }, [zoneId, firstZoneId, setParams]);

  return <ScreenFrame id="myZone">
    <div className="workspace-strip">
      <label className="field"><span>{t("forms.selectZone")}</span>
        <select value={zoneId} onChange={(event) => changeZone(event.currentTarget.value)} disabled={zones.isLoading || zones.isError || !zones.data?.length}>
          <option value="">{zones.data?.length ? t("common.select") : t("forms.noZones")}</option>
          {zones.data?.map((item) => <option value={item.zone_id} key={item.zone_id}>{item.name}</option>)}
        </select>
      </label>
      <RunIdField value={runId} onChange={setRunId} />
    </div>
    {zones.isLoading && <Loading />}
    {zones.isError && <ErrorState error={zones.error} onRetry={() => void zones.refetch()} />}
    {!zones.isLoading && !zones.isError && zones.data?.length === 0 && <Empty title={t("forms.noZones")} />}

    <div className="zone-grid">
      <section className="content-card" aria-labelledby="territory-title">
        <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="location" /></span><h2 id="territory-title">{t("screens.myZone.territory")}</h2></div>
        {!zoneId && <InsufficientData detail={t("forms.selectZone")} />}
        {zone.isLoading && <Loading />}
        {zone.isError && <ErrorState error={zone.error} onRetry={() => void zone.refetch()} />}
        {zone.data && <>
          <dl className="context-list">
            <dt>{t("forms.selectZone")}</dt><dd>{zone.data.name}</dd>
            <dt>{t("screens.myZone.region")}</dt><dd>{/jocotan|camotan/i.test(zone.data.name) ? t("screens.myZone.chortiRegion") : t("screens.myZone.regionLabel")}</dd>
          </dl>
          <details className="chart-data-details">
            <summary>{t("screens.myZone.technicalIdentifiers")}</summary>
            <dl className="context-list">
              <dt>{t("screens.myZone.zoneIdentifier")}</dt><dd><code>{zone.data.zone_id}</code></dd>
              <dt>{t("screens.myZone.regionIdentifier")}</dt><dd><code>{zone.data.region_id}</code></dd>
            </dl>
          </details>
          <div className="indicator-list">
            {zone.data.elevation && <Indicator indicator={zone.data.elevation} />}
            {zone.data.slope && <Indicator indicator={zone.data.slope} />}
          </div>
          {(zone.data.elevation?.provisional || zone.data.slope?.provisional) && <ProvisionalBanner />}
          {!zone.data.elevation && !zone.data.slope && <InsufficientData detail={t("common.notAvailable")} />}
          <p className="privacy-note">{t("privacy.noExactGeometry")}</p>
        </>}
      </section>

      <section className="content-card" aria-labelledby="agriculture-title">
        <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="crop" /></span><h2 id="agriculture-title">{t("screens.myZone.agriculture")}</h2></div>
        {zone.isLoading && <Loading />}
        {zone.data && <ZoneContextBlock context={zone.data.context} parcel={parcel.data} />}
      </section>
    </div>

    <section className="content-card" aria-labelledby="sources-title">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="source" /></span><h2 id="sources-title">{t("screens.myZone.sources")}</h2></div>
      {quality.isLoading && <Loading />}
      {quality.isError && <ErrorState error={quality.error} onRetry={() => void quality.refetch()} />}
      {quality.data && <DataQualityBlock quality={quality.data} sources={zone.data?.sources} />}
      {zone.data && /jocotan|camotan/i.test(zone.data.name) && <StationValidationNotice zoneId={zoneId} />}
      {!zoneId && <Empty title={t("common.empty")} detail={t("forms.selectZone")} />}
    </section>

    <section className="content-card" aria-labelledby="soil-title">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="soil" /></span><h2 id="soil-title">{t("soil.heading")}</h2></div>
      {zone.data && /jocotan|camotan/i.test(zone.data.name) && <section aria-labelledby="soilgrids-title">
        <h3 id="soilgrids-title">{t("soil.soilgridsTitle")}</h3>
        {soilGrids.isLoading && <Loading />}
        {soilGrids.isError && <ErrorState error={soilGrids.error} onRetry={() => void soilGrids.refetch()} />}
        {soilGrids.data && (soilGrids.data.status !== "ok"
          ? <p role="status">{t("soil.soilgridsUnavailable")}</p>
          : <>
            <p>{t("soil.soilgrids_note")}</p>
            <p className="chart-caption">{t("soil.depth")}: {soilGrids.data.depth} · ISRIC SoilGrids v2.0 · {t("soil.soilgrids_points")}: {soilGrids.data.points ?? "—"}</p>
            <div className="table-scroll"><table className="data-table" data-testid="soilgrids-table">
              <thead><tr><th scope="col">{t("soil.property")}</th><th scope="col">{t("soil.value")}</th></tr></thead>
              <tbody>{Object.entries(soilGrids.data.properties).map(([code, item]) => <tr key={code}>
                <th scope="row">{t(`soil.soilgrids_${code}`, { defaultValue: code })}</th>
                <td>{item.value == null ? t("soil.notAvailable") : `${new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(item.value)} ${item.unit}`}</td>
              </tr>)}</tbody>
            </table></div>
          </>)}
      </section>}
      {demo ? <p className="chart-caption" data-testid="demo-parcel-note">{t("soil.soilgrids_demo")}</p> : <QueryField id="parcel-id" label={t("soil.parcelId")} value={parcelId} onChange={setParcelId} placeholder="parcel_id" help={t("soil.parcelIdHelp")} />}
      {zone.data && /jocotan|camotan/i.test(zone.data.name) && <>
        <PlantingValidation zoneId={zoneId} onDate={setPlantingDate} />
        <RainyOnsetSandbox zoneId={zoneId} plantingDate={plantingDate} />
      </>}
      {parcel.isError && <ErrorState error={parcel.error} />}
      {soil.isLoading && <Loading />}
      {soil.isError && <ErrorState error={soil.error} onRetry={() => void soil.refetch()} />}
      {!demo && !parcelId && <Empty title={t("soil.noParcel")} />}
      {parcelId && !soil.isLoading && !soil.isError && <SoilStatusTable properties={soil.data ?? []} />}
      {!demo && <>
        <SoilUpload parcelId={parcelId} />
        <SoilDeclarationForm parcelId={parcelId} />
        <DeleteParcelControl parcelId={parcelId} onDeleted={clearParcel} />
      </>}
    </section>

    <section className="content-card" aria-labelledby="voi-title">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="question" /></span><h2 id="voi-title">{t("soil.voiTitle")}</h2></div>
      {soilVoi.isError && <ErrorState error={soilVoi.error} onRetry={() => soilVoi.reset()} />}
      {runId && ph?.status !== "medido" && <button className="button" type="button" disabled={soilVoi.isPending} onClick={() => soilVoi.mutate()}>
        {soilVoi.isPending ? t("common.loading") : t("soil.evaluateVoi")}
      </button>}
      {ph?.status === "medido" && <VoiPanel result={null} phStatus={ph.status} />}
      {ph?.status !== "medido" && soilVoi.data && <VoiPanel result={soilVoi.data} phStatus={ph?.status} />}
      {ph?.status !== "medido" && !runId && !soilVoi.data && <VoiPanel result={null} phStatus={ph?.status} />}
      {runId && soilVoi.isIdle && ph?.status !== "medido" && <p className="chart-caption">{t("soil.voiUnavailable")}</p>}
    </section>
    <section className="content-card" aria-labelledby="sources-status-title">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="source" /></span><h2 id="sources-status-title">Data sources: what is really connected</h2></div>
      <SourceStatus />
    </section>
  </ScreenFrame>;
}
