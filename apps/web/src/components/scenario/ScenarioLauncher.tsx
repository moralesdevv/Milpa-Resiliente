import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { useJob, useRunScenariosJob } from "../../api/queries";
import { useSession } from "../../api/session";
import { ErrorState } from "../common/states";

const scenarioIdPattern = /^T[+-]?\d+(?:\.\d+)?_P[+-]\d+_D\+\d+_H(?:rh|ea)$/;

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
  const [custom, setCustom] = useState("");
  const status = job.data?.status;

  useEffect(() => {
    if (status === "ok") {
      void queryClient.invalidateQueries({ queryKey: ["run-scenarios", runId] });
      void queryClient.invalidateQueries({ queryKey: ["run-summary", runId] });
    }
  }, [status, queryClient, runId]);

  const customValid = scenarioIdPattern.test(custom.trim());
  const submitCustom = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (customValid) launch.mutate({ scenario_ids: [custom.trim()] });
  };
  const busy = launch.isPending || status === "queued" || status === "running";

  return <section className="form-card scenario-launcher" aria-labelledby="scenario-launcher-title" data-testid="scenario-launcher">
    <h3 id="scenario-launcher-title">{t("scenario.launchTitle")}</h3>
    <p className="chart-caption">{t("scenario.launchHelp")}</p>
    <div className="inline-actions">
      <button className="button" type="button" disabled={!runId || !session || busy} onClick={() => launch.mutate({})}>{t("scenario.launchGrid")}</button>
    </div>
    <form className="inline-field" onSubmit={submitCustom}>
      <label className="field"><span>{t("scenario.customId")}</span>
        <input type="text" value={custom} onChange={(event) => setCustom(event.currentTarget.value)} placeholder="T+2_P-20_D+20_Hrh" aria-describedby="scenario-grammar" />
      </label>
      <button className="button button--secondary" type="submit" disabled={!runId || !session || busy || !customValid}>{t("scenario.launchOne")}</button>
    </form>
    <small id="scenario-grammar">{t("scenario.grammar")}</small>
    {!session && <p className="chart-caption">{t("scenario.signInToLaunch")}</p>}
    {launch.isError && <ErrorState error={launch.error} />}
    {launch.data && <p role="status" data-testid="scenario-job-status">
      {t("scenario.jobStatus")}: {t(`jobs.${status ?? "queued"}`)}
      {job.data?.progress != null && ` · ${Math.round(job.data.progress * 100)} %`}
    </p>}
    {status === "failed" && <ErrorState error={job.data?.error ?? null} />}
  </section>;
}
