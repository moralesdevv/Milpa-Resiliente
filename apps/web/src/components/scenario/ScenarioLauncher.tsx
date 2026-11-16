import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { useJob, useRunScenariosJob } from "../../api/queries";
import { useSession } from "../../api/session";
import { ErrorState } from "../common/states";

// Values of the scientific engine's standard grid (milpa_core.standard_grid): 3 x 3 x 3 combinations
// (+ humidity assumption when the temperature changes). The selectors below can only build valid ids.
const TEMPERATURE = [0, 1, 2] as const;
const PRECIPITATION = [0, -10, -20] as const;
const DELAY = [0, 10, 20] as const;
const sign = (n: number) => (n < 0 ? "-" : "+");

export function buildScenarioId(dt: number, p: number, d: number, humidity: "rh" | "ea"): string {
  return `T+${dt}_P${sign(p)}${Math.abs(p)}_D+${d}_H${dt === 0 ? "na" : humidity}`;
}

/**
 * Launches the scenario job on the backend and follows its progress.
 * Nothing is calculated here; combinations not computed yet need a job.
 */
export function ScenarioLauncher({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const session = useSession();
  const queryClient = useQueryClient();
  const launch = useRunScenariosJob(runId || null);
  const job = useJob(launch.data?.job_id ?? null);
  const [dt, setDt] = useState<number>(2);
  const [precip, setPrecip] = useState<number>(-20);
  const [delay, setDelay] = useState<number>(20);
  const [humidity, setHumidity] = useState<"rh" | "ea">("rh");
  const status = job.data?.status;

  useEffect(() => {
    if (status === "ok") {
      void queryClient.invalidateQueries({ queryKey: ["run-scenarios", runId] });
      void queryClient.invalidateQueries({ queryKey: ["run-summary", runId] });
    }
  }, [status, queryClient, runId]);

  const chosenId = buildScenarioId(dt, precip, delay, humidity);
  const chosenIsBase = dt === 0 && precip === 0 && delay === 0;
  const submitCustom = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!chosenIsBase) launch.mutate({ scenario_ids: [chosenId] });
  };
  const busy = launch.isPending || status === "queued" || status === "running";

  return <section className="form-card scenario-launcher" aria-labelledby="scenario-launcher-title" data-testid="scenario-launcher">
    <h3 id="scenario-launcher-title">{t("scenario.launchTitle")}</h3>
    <p className="chart-caption">{t("scenario.launchHelp")}</p>
    <div className="inline-actions">
      <button className="button" type="button" disabled={!runId || !session || busy} onClick={() => launch.mutate({})}>{t("scenario.launchGrid")}</button>
    </div>
    <form className="scenario-form" onSubmit={submitCustom} aria-label={t("scenario.launchOne")}>
      <label className="field"><span>{t("scenario.temperature")}</span>
        <select value={dt} onChange={(event) => setDt(Number(event.currentTarget.value))}>
          {TEMPERATURE.map((v) => <option key={v} value={v}>{v === 0 ? t("scenario.noChange") : `+${v} °C`}</option>)}
        </select></label>
      <label className="field"><span>{t("scenario.precipitationFactor")}</span>
        <select value={precip} onChange={(event) => setPrecip(Number(event.currentTarget.value))}>
          {PRECIPITATION.map((v) => <option key={v} value={v}>{v === 0 ? t("scenario.noChange") : `${v} %`}</option>)}
        </select></label>
      <label className="field"><span>{t("scenario.onsetDelay")}</span>
        <select value={delay} onChange={(event) => setDelay(Number(event.currentTarget.value))}>
          {DELAY.map((v) => <option key={v} value={v}>{v === 0 ? t("scenario.noChange") : t("scenario.days", { count: v })}</option>)}
        </select></label>
      <label className="field"><span>{t("scenario.humidity")}</span>
        <select value={dt === 0 ? "na" : humidity} disabled={dt === 0} onChange={(event) => setHumidity(event.currentTarget.value as "rh" | "ea")}>
          {dt === 0 && <option value="na">{t("scenario.humidityModes.not_applicable")}</option>}
          <option value="rh">{t("scenario.humidityModes.constant_rh")}</option>
          <option value="ea">{t("scenario.humidityModes.constant_ea")}</option>
        </select></label>
      <button className="button button--secondary" type="submit" disabled={!runId || !session || busy || chosenIsBase}>{t("scenario.launchOne")}</button>
    </form>
    <small id="scenario-grammar">{chosenIsBase ? t("scenario.baseAlready") : t("scenario.chosenId", { id: chosenId })}</small>
    {launch.isError && <ErrorState error={launch.error} />}
    {launch.data && <p role="status" data-testid="scenario-job-status">
      {t("scenario.jobStatus")}: {t(`jobs.${status ?? "queued"}`)}
      {job.data?.progress != null && ` · ${Math.round(job.data.progress * 100)} %`}
    </p>}
    {status === "failed" && <ErrorState error={job.data?.error ?? null} />}
  </section>;
}
