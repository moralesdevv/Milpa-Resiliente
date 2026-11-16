import { useTranslation } from "react-i18next";

export const KINDS = ["observed", "satellite", "modelled", "assumption", "simulation", "fictitious"] as const;
export type Kind = (typeof KINDS)[number];

/** A text chip (never colour alone) that says what kind of figure follows: observed, satellite, modelled… */
export function KindChip({ kind }: { kind: Kind }) {
  const { t } = useTranslation();
  return <span className={`kind-chip kind-chip--${kind}`} data-kind={kind}>{t(`agronomy.kinds.${kind}`)}</span>;
}

export function KindLegend() {
  const { t } = useTranslation();
  return <details className="kind-legend">
    <summary>{t("agronomy.legendTitle")}</summary>
    <dl>
      {KINDS.map((kind) => <div key={kind}><dt><KindChip kind={kind} /></dt><dd>{t(`agronomy.kindsHelp.${kind}`)}</dd></div>)}
    </dl>
  </details>;
}
