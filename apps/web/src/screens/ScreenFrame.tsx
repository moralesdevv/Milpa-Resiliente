import type { ReactNode } from "react";
import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { HeroArt } from "../components/common/HeroArt";
import { Loading, ErrorState } from "../components/common/states";

export function ScreenFrame({ id, children }: { id: string; children: ReactNode }) {
  const { t } = useTranslation();
  return <div className="screen" data-screen={id}>
    <header className="screen-heading">
      <HeroArt />
      <div className="screen-heading__text">
        <h1>{t(`screens.${id}.title`)}</h1>
        <p className="screen-question">{t(`screens.${id}.question`)}</p>
        <p className="screen-tag">MILPA RESILIENTE · DEMO</p>
      </div>
    </header>
    {children}
  </div>;
}

export function QueryField({ id, label, value, onChange, placeholder, help }: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  help?: string;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(value);
  const [seenValue, setSeenValue] = useState(value);
  // Re-sync the draft when the URL value changes from outside (React-recommended pattern, no effect needed).
  if (value !== seenValue) {
    setSeenValue(value);
    setDraft(value);
  }
  return <div className="field field--run-id">
    <label htmlFor={id}>{label}</label>
    <span className="inline-field">
      <input id={id} type="text" inputMode="text" autoComplete="off" value={draft} onChange={(event) => setDraft(event.currentTarget.value)} onBlur={() => onChange(draft.trim())} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onChange(draft.trim()); } }} placeholder={placeholder} aria-describedby={help ? `${id}-help` : undefined} />
      <button className="button button--secondary button--compact" type="button" onClick={() => onChange(draft.trim())}>{t("common.apply")}</button>
    </span>
    {help && <small id={`${id}-help`}>{help}</small>}
  </div>;
}

export function RunIdField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  return <QueryField id="shared-run-id" label={t("forms.runId")} value={value} onChange={onChange} placeholder="run_id" help={t("forms.noRuns")} />;
}

export function useSharedQueryParam(key: string, fallback = "") {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) ?? fallback;
  const setValue = useCallback((nextValue: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (nextValue) next.set(key, nextValue);
      else next.delete(key);
      return next;
    }, { replace: true });
  }, [key, setParams]);
  return [value, setValue] as const;
}

export function QueryFeedback({ isLoading, error, retry }: { isLoading: boolean; error: unknown; retry?: () => void }) {
  if (isLoading) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={retry} />;
  return null;
}
