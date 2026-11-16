import { useTranslation } from "react-i18next";

import { useRun } from "../../api/queries";
import type { components } from "../../api/types.gen";
import { ErrorState, InsufficientData, Loading, ProvisionalBanner } from "../common/states";

type RunOut = components["schemas"]["RunOut"];

function isRunDto(value: unknown): value is RunOut {
  return typeof value === "object" && value !== null && "mode" in value && "label" in value && "mode_reasons" in value;
}

/** Shows the calculation mode decided by the engine, never decided by the UI. */
export function RunHeader({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const run = useRun(runId || null);
  if (!runId) return null;
  if (run.isLoading) return <Loading />;
  if (run.isError) return <ErrorState error={run.error} onRetry={() => void run.refetch()} />;
  if (!isRunDto(run.data)) return <InsufficientData detail={t("run.noMode")} />;

  const { label, mode_reasons: reasons, sandbox, synthetic_fixture: synthetic } = run.data;
  return <section className="run-header" aria-label={t("run.title")} data-testid="run-header">
    <div className="run-header__main">
      <span className="mode-chip" data-testid="mode-label">{t(`mode.${label}`)}</span>
      <code title={run.data.run_id} aria-label={run.data.run_id}>{t("run.shortId", { id: run.data.run_id.slice(0, 8) })}</code>
    </div>
    {reasons.length > 0 && <p className="run-header__reasons">
      {t("run.modeReasons")}: {reasons.map((reason) => reason.startsWith("catalog:") ? t("run.reasonCatalog", { variety: reason.slice(8).replace(/_/g, " ") }) : t(`run.reasons.${reason}`, reason)).join("; ")}
    </p>}
    {sandbox && <ProvisionalBanner>{t("run.sandbox")}</ProvisionalBanner>}
    {synthetic && <ProvisionalBanner>{t("run.syntheticFixture")}</ProvisionalBanner>}
  </section>;
}
