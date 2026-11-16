import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { useCreateReport, useJob, useReport, useRun } from "../api/queries";
import { useSession } from "../api/session";
import type { components } from "../api/types.gen";
import { Empty, ErrorState, InsufficientData, Loading } from "../components/common/states";
import { RunHeader } from "../components/run/RunHeader";
import { QueryField, RunIdField, ScreenFrame, useSharedQueryParam } from "./ScreenFrame";
import { Icon } from "../components/common/Icon";

type Privacy = components["schemas"]["ReportCreate"]["privacy_level"];
type Locale = components["schemas"]["ReportCreate"]["locale"];
type Section = Record<string, unknown>; // secciones: forma definida por R2 (report_model)

const reproducibilityFields = ["code_version", "region_config_hash", "catalog_hash", "data_hash", "params_hash"] as const;

function text(section: Section, key: string): string | null {
  const value = (section as Record<string, unknown>)[key];
  return typeof value === "string" && value ? value : null;
}

function SectionBlock({ section, english, showBoth }: { section: Section; english: boolean; showBoth: boolean }) {
  const { t } = useTranslation();
  const title = (english ? text(section, "title_en") : text(section, "title_es")) ?? text(section, "title_es") ?? text(section, "title") ?? t("common.unknownShape");
  const body = (english ? text(section, "body_en") : text(section, "body_es")) ?? text(section, "body_es");
  const bodyEn = text(section, "body_en");
  return <article className="report-section">
    <h4>{title}</h4>
    {body && <p>{body}</p>}
    {showBoth && !english && bodyEn && <p lang="en" className="report-section__english">{bodyEn}</p>}
  </article>;
}

export function ReportScreen() {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  const session = useSession();
  const [runId, setRunId] = useSharedQueryParam("runId");
  const [rankingId, setRankingId] = useSharedQueryParam("rankingId");
  const [reportId, setReportId] = useSharedQueryParam("reportId");
  const [privacy, setPrivacy] = useState<Privacy>("internal");
  const [locale, setLocale] = useState<Locale>("es+en");
  const create = useCreateReport();
  const job = useJob(create.data?.job_id ?? null);
  const report = useReport(reportId || null);
  const run = useRun(runId || null);
  const reportData = report.data;
  const reportIdValue = job.data?.status === "ok" ? job.data.result?.report_id : null;
  const jobReportId = typeof reportIdValue === "string" ? reportIdValue : null;

  useEffect(() => {
    if (jobReportId && jobReportId !== reportId) setReportId(jobReportId);
  }, [jobReportId, reportId, setReportId]);

  const runData = run.data as Record<string, unknown> | undefined;
  const hashes = reproducibilityFields.flatMap((key) => {
    const value = runData?.[key];
    return typeof value === "string" ? [{ key, value }] : [];
  });
  const generating = create.isPending || job.data?.status === "queued" || job.data?.status === "running";
  const privacyShown: Privacy = report.data?.privacy_level ?? privacy;
  const outlineMain = t("report.outlineMain", { returnObjects: true }) as unknown as string[];
  const outlineAnnex = t("report.outlineAnnex", { returnObjects: true }) as unknown as string[];

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!runId) return;
    create.mutate({ run_id: runId, ranking_id: rankingId || null, locale, privacy_level: privacy });
  };

  return <ScreenFrame id="report">
    {runId && <RunHeader runId={runId} />}
    <div className="report-layout">
      <form className="content-card report-controls" onSubmit={submit} aria-labelledby="report-controls-title">
        <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="document" /></span><h2 id="report-controls-title">{t("screens.report.template")}</h2></div>
        <RunIdField value={runId} onChange={setRunId} />
        <QueryField id="ranking-id" label={t("report.rankingId")} value={rankingId} onChange={setRankingId} />
        <label className="field"><span>{t("report.privacy")}</span>
          <select value={privacy} onChange={(event) => setPrivacy(event.currentTarget.value as Privacy)}>
            <option value="internal">{t("report.internal")}</option><option value="public">{t("report.public")}</option>
          </select>
        </label>
        <label className="field"><span>{t("report.locale")}</span>
          <select value={locale} onChange={(event) => setLocale(event.currentTarget.value as Locale)}>
            <option value="es">{t("report.localeEs")}</option><option value="es+en">{t("report.localeEsEn")}</option>
          </select>
        </label>
        <button className="button" type="submit" disabled={!runId || !session || generating}>{generating ? t("common.loading") : t("report.generate")}</button>
        {!session && <p className="chart-caption">{t("report.signInToGenerate")}</p>}
        {create.isError && <ErrorState error={create.error} onRetry={() => create.reset()} />}
        {create.data && <p className="notice" role="status" data-testid="report-job-status">{t("report.jobStatus")}: {t(`jobs.${job.data?.status ?? "queued"}`)}{job.data?.progress != null && ` · ${Math.round(job.data.progress * 100)} %`}</p>}
        {job.data?.status === "failed" && <ErrorState error={job.data.error ?? null} />}
        <p className="chart-caption">{t("report.templateNote")}</p>
      </form>

      <section className="report-preview" aria-labelledby="report-preview-title">
        <div className="report-sheet" data-testid="report-sheet" data-privacy={privacyShown}>
          <div className="report-sheet__topline"><strong>{t("app.title")}</strong><span>{t("report.privacy")}: {t(privacyShown === "public" ? "report.public" : "report.internal")}</span></div>
          <header><p className="eyebrow">{t("screens.report.mainPage")}</p><h2 id="report-preview-title">{t("screens.report.title")}</h2>
            <p data-testid="not-automatic">{t("common.notAutomaticRecommendation")}</p></header>
          {privacyShown === "public" && <p className="privacy-note" data-testid="public-privacy-note">{t("report.publicPrivacy")}</p>}
          {report.isLoading && <Loading />}
          {reportData ? <>
            <section aria-label={t("report.summary")}>
              <h3>{t("report.summary")}</h3>
              {reportData.sections.map((section, index) => <SectionBlock key={index} section={section} english={english} showBoth={reportData.locale === "es+en"} />)}
              {reportData.sections.length === 0 && <Empty title={t("common.notAvailable")} />}
            </section>
            <section aria-label={t("report.annex")}>
              <h3>{t("report.annex")}</h3>
              {reportData.annex.map((section, index) => <SectionBlock key={index} section={section} english={english} showBoth={reportData.locale === "es+en"} />)}
              {reportData.annex.length === 0 && <Empty title={t("common.notAvailable")} />}
            </section>
            <section aria-label={t("report.humanDecisions")}>
              <h3>{t("report.humanDecisions")}</h3>
              <p>{t("report.humanDecisionsText")}</p>
            </section>
          </> : <>
            <Empty title={t("report.notGenerated")} />
            <details className="report-outline"><summary>{t("report.expectedContent")}</summary>
              <h4>{t("screens.report.mainPage")}</h4>
              <ul className="template-list">{outlineMain.map((item) => <li key={item}>{item}</li>)}</ul>
              <h4>{t("report.annex")}</h4>
              <ul className="template-list">{outlineAnnex.map((item) => <li key={item}>{item}</li>)}</ul>
            </details>
          </>}
          <div className="report-sheet__footer" data-testid="report-footer">
            <span>run_id: {runId || t("common.notAvailable")}</span>
            <span>{run.isLoading ? t("common.loading") : hashes.map(({ key, value }) => `${key}: ${value}`).join(" · ") || (run.data ? t("report.hashesPending") : t("common.notAvailable"))}</span>
          </div>
        </div>
      </section>
    </div>

    <section className="content-card" aria-labelledby="existing-report-title">
      <div className="section-heading"><span className="section-icon" aria-hidden="true"><Icon name="source" /></span><h2 id="existing-report-title">{t("report.reportId")}</h2></div>
      <div className="report-lookup">
        <QueryField id="report-id" label={t("report.reportId")} value={reportId} onChange={setReportId} />
      </div>
      {report.isError && <ErrorState error={report.error} onRetry={() => void report.refetch()} />}
      {report.data && <article className="report-metadata" data-testid="report-metadata">
        <dl className="context-list">
          <dt>{t("report.reportId")}</dt><dd><code>{report.data.report_id}</code></dd>
          <dt>{t("report.runId")}</dt><dd><code>{report.data.run_id}</code></dd>
          <dt>{t("report.privacy")}</dt><dd>{t(report.data.privacy_level === "public" ? "report.public" : "report.internal")}</dd>
          <dt>{t("report.hash")}</dt><dd><code className="hash-value">{report.data.sha256}</code></dd>
        </dl>
        {report.data.pdf_url && <a className="button" href={report.data.pdf_url} target="_blank" rel="noreferrer">{t("report.downloadPdf")}</a>}
      </article>}
      {!reportId && <InsufficientData detail={t("report.notGenerated")} />}
      <section className="reproducibility-card" aria-labelledby="run-hashes-title">
        <h3 id="run-hashes-title">{t("report.reproducibility")}</h3>
        {run.isLoading && <Loading />}
        {run.isError && <ErrorState error={run.error} onRetry={() => void run.refetch()} />}
        {hashes.length ? <dl className="context-list">{hashes.map(({ key, value }) => <div className="hash-entry" key={key}><dt>{key}</dt><dd><code className="hash-value">{value}</code></dd></div>)}</dl> : run.data && <InsufficientData detail={t("report.hashesPending")} />}
        {!runId && <Empty title={t("forms.selectRun")} />}
      </section>
    </section>
  </ScreenFrame>;
}
