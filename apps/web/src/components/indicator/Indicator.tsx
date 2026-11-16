import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";

type IndicatorData = components["schemas"]["IndicatorNumber"] | components["schemas"]["IndicatorInteger"];
type ProvenanceData = components["schemas"]["ProvenanceInfo"];

const provenanceKeys: Record<components["schemas"]["Provenance"], string> = {
  medido: "provenance.measured",
  satelital: "provenance.satellite",
  estimado: "provenance.estimated",
  modelado: "provenance.modelled",
  declarado: "provenance.declared",
  desconocido: "provenance.unknown",
};

export function EvidenceBadge({ evidence, provenance, short = false }: { evidence: IndicatorData["provenance"]["evidence"]; provenance: IndicatorData["provenance"]["provenance"]; short?: boolean }) {
  const { t } = useTranslation();
  const full = evidence ? t("provenance.evidenceLevel", { level: evidence }) : t("provenance.noEvidence");
  return <span className={`evidence-badge evidence-badge--${evidence ?? "unknown"}`}>
    {short && evidence
      ? <span><span aria-hidden="true">{t("provenance.evidenceShort", { level: evidence })}</span><span className="visually-hidden">{full}</span></span>
      : <span>{full}</span>}
    <span>{t(provenanceKeys[provenance])}</span>
  </span>;
}

function useFormattedValue(indicator: IndicatorData) {
  const { i18n, t } = useTranslation();
  const value = indicator.value === null
    ? t("common.notAvailable")
    : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(indicator.value);
  const label = i18n.language.startsWith("en") ? indicator.label_en : indicator.label_es;
  return { value, label };
}

/**
 * Every figure shown to a person travels through this component: value, unit,
 * evidence level, provenance mark and the full provenance panel.
 * `compact` drops the visible label (a table header supplies it) and opens the
 * provenance in a floating panel so tables stay readable; nothing is removed:
 * the label, the reason and the panel stay available to assistive technology.
 */
export function Indicator({ indicator, includeMissingPct = true, compact = false }: { indicator: IndicatorData; includeMissingPct?: boolean; compact?: boolean }) {
  const { t } = useTranslation();
  const { value, label } = useFormattedValue(indicator);

  if (compact) {
    return <span className="indicator indicator--compact" data-indicator-code={indicator.code}>
      <span className="indicator__value"><span className="visually-hidden">{label}: </span>{value}<span className="indicator__unit">{indicator.unit && ` ${indicator.unit}`}</span></span>
      <span className="indicator__meta">
        <EvidenceBadge evidence={indicator.provenance.evidence} provenance={indicator.provenance.provenance} short />
        {indicator.provisional && <span className="indicator__flag" aria-hidden="true" title={t("common.provisional")}>{t("common.provisionalAbbr")}</span>}
        <ProvenancePanel provenance={indicator.provenance} includeMissingPct={includeMissingPct} floating />
      </span>
      {indicator.provisional && <span className="visually-hidden indicator__reason">{indicator.reason ?? t("common.provisional")}</span>}
    </span>;
  }

  return <div className="indicator" data-indicator-code={indicator.code}>
    <div className="indicator__main">
      <span className="indicator__label">{label}</span>
      <span className="indicator__value">{value}<span className="indicator__unit">{indicator.unit && ` ${indicator.unit}`}</span></span>
    </div>
    <EvidenceBadge evidence={indicator.provenance.evidence} provenance={indicator.provenance.provenance} />
    <ProvenancePanel provenance={indicator.provenance} includeMissingPct={includeMissingPct} />
    {indicator.provisional && <span className="indicator__reason">{indicator.reason ?? t("common.provisional")}</span>}
  </div>;
}

/**
 * Provenance details. `floating` shows them in a panel anchored to the trigger and fixed to the
 * viewport, so a table's scroll container never clips it. It closes on Escape, outside click,
 * scroll and resize; Escape returns focus to the trigger.
 */
export function ProvenancePanel({ provenance, includeMissingPct = true, floating = false }: { provenance: ProvenanceData; includeMissingPct?: boolean; floating?: boolean }) {
  const { i18n, t } = useTranslation();
  const ref = useRef<HTMLDetailsElement>(null);
  const [place, setPlace] = useState<CSSProperties | undefined>();
  const period = provenance.period;

  const close = useCallback(() => {
    if (ref.current) ref.current.open = false;
  }, []);

  useEffect(() => {
    if (!floating) return;
    const details = ref.current;
    if (!details) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && details.open) {
        close();
        details.querySelector("summary")?.focus();
      }
    };
    const onPointer = (event: PointerEvent) => {
      if (details.open && event.target instanceof Node && !details.contains(event.target)) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [floating, close]);

  const onToggle = floating
    ? () => {
      const details = ref.current;
      if (!details?.open) return;
      const anchor = details.getBoundingClientRect();
      const width = Math.min(360, window.innerWidth - 24);
      const left = Math.min(Math.max(12, anchor.left), window.innerWidth - width - 12);
      const below = anchor.bottom + 8;
      const top = below + 280 > window.innerHeight ? Math.max(12, anchor.top - 8 - 280) : below;
      setPlace({ position: "fixed", top, left, width, maxHeight: Math.max(160, window.innerHeight - top - 12) });
    }
    : undefined;

  return <details ref={ref} className={`provenance-panel${floating ? " provenance-panel--floating" : ""}`} onToggle={onToggle}>
    <summary>{t("provenance.details")}</summary>
    <dl style={floating ? place : undefined}>
      <dt>{t("provenance.sources")}</dt>
      <dd>{provenance.sources.length
        ? provenance.sources.map((source) => <span className="provenance-source" key={`${source.code}:${source.product_name}`}>
          {source.institution} · {source.product_name}{source.version ? ` · ${source.version}` : ""}
          {source.is_nasa ? "" : ` · ${t("provenance.notNasa")}`}
          {source.citation && <span> · {source.citation}</span>}
          {source.url && <a href={source.url} target="_blank" rel="noreferrer">{source.url}</a>}
        </span>)
        : t("common.notAvailable")}</dd>
      <dt>{t("provenance.datasetVersion")}</dt>
      <dd>{provenance.dataset_version ?? t("common.notAvailable")}</dd>
      <dt>{t("provenance.period")}</dt>
      <dd>{period ? `${period.start ?? "?"} — ${period.end ?? "?"}` : t("common.notAvailable")}</dd>
      <dt>{t("provenance.resolution")}</dt>
      <dd>{[provenance.spatial_res, provenance.temporal_res].filter(Boolean).join(" · ") || t("common.notAvailable")}</dd>
      <dt>{t("provenance.method")}</dt>
      <dd>{provenance.method}</dd>
      <dt>{t("provenance.retrieved")}</dt>
      <dd>{provenance.retrieved_at ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(provenance.retrieved_at)) : t("common.notAvailable")}</dd>
      {includeMissingPct && <><dt>{t("provenance.missing")}</dt>
      <dd>{provenance.missing_pct ? <Indicator indicator={provenance.missing_pct} includeMissingPct={false} /> : t("common.notAvailable")}</dd></>}
      <dt>{t("provenance.assumptions")}</dt>
      <dd>{provenance.assumptions.length ? provenance.assumptions.join("; ") : t("common.none")}</dd>
      <dt>{t("provenance.limitations")}</dt>
      <dd>{provenance.limitations.length ? provenance.limitations.join("; ") : t("common.none")}</dd>
      <dt>{t("provenance.rule")}</dt>
      <dd><code>{provenance.evidence_rule}</code></dd>
      <dt>{t("provenance.runId")}</dt>
      <dd>{provenance.run_id ?? t("common.notAvailable")}</dd>
    </dl>
  </details>;
}
