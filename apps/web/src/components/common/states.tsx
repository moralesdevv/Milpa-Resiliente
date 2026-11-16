import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/client";

export function Loading({ label }: { label?: string }) {
  const { t } = useTranslation();
  return <div className="state-card" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{label ?? t("common.loading")}</div>;
}

export function Empty({ title, detail }: { title?: string; detail?: string }) {
  const { t } = useTranslation();
  return <section className="state-card state-card--empty" role="status">
    <span className="state-mark" aria-hidden="true">—</span>
    <div><h3>{title ?? t("common.empty")}</h3>{detail && <p>{detail}</p>}</div>
  </section>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  const apiError = error as Partial<ApiError> | null;
  const code = typeof apiError?.code === "string" ? apiError.code : "REQUEST_FAILED";
  const detail = error instanceof ApiError && error.hint ? error.hint : t("common.error");

  return <section className="state-card state-card--error" role="alert">
    <div><h3>{t("common.error")}</h3><p>{detail}</p><code>{code}</code></div>
    {onRetry && <button className="button button--secondary" type="button" onClick={onRetry}>{t("common.retry")}</button>}
  </section>;
}

export function InsufficientData({ title, detail, missing }: { title?: string; detail?: string; missing?: string[] }) {
  const { t } = useTranslation();
  return <section className="state-card state-card--insufficient" role="status">
    <span className="state-mark" aria-hidden="true">?</span>
    <div><h3>{title ?? t("common.insufficientData")}</h3>
      {detail && <p>{detail}</p>}
      {missing && missing.length > 0 && <ul>{missing.map((item) => <li key={item}>{item}</li>)}</ul>}
    </div>
  </section>;
}

export function ProvisionalBanner({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  return <aside className="provisional-banner" role="note">
    <span aria-hidden="true">!</span>
    <p>{children ?? t("common.provisional")}</p>
  </aside>;
}
