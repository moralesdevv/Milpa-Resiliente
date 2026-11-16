import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Indicator } from "../indicator/Indicator";

type StabilityFlag = components["schemas"]["StabilityFlag"];
type StabilityData = components["schemas"]["StabilityDTO"];

const flags: StabilityFlag[] = ["stable", "moderate", "unstable", "insufficient"];
const marks: Record<StabilityFlag, string> = { stable: "●", moderate: "◐", unstable: "○", insufficient: "?" };

export function StabilityMeter({ stability, flag }: { stability?: StabilityData; flag?: StabilityFlag }) {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  const activeFlag = stability?.flag ?? flag ?? "insufficient";
  const maxShare = stability ? Math.max(0, ...Object.values(stability.top1_share).map((item) => item.value ?? 0)) : 0;

  return <section className={`stability-meter stability-meter--${activeFlag}`} aria-labelledby="stability-title" data-testid="stability-meter" data-flag={activeFlag}>
    <div className="stability-meter__header">
      <div><p className="eyebrow">{t("ranking.stability")}</p><h3 id="stability-title">{t(`ranking.stabilityFlags.${activeFlag}`)}</h3></div>
      <span className="stability-meter__mark" aria-hidden="true">{marks[activeFlag]}</span>
    </div>
    <ol className="stability-meter__scale" aria-label={t("ranking.stabilityScale")}>
      {flags.map((item) => <li key={item} className={item === activeFlag ? "is-active" : ""}><span aria-hidden="true">{marks[item]}</span> {t(`ranking.stabilityFlags.${item}`)}</li>)}
    </ol>
    {stability && Object.keys(stability.top1_share).length > 0 && <div className="stability-meter__indicators">
      <h4>{t("ranking.top1Share")}</h4>
      <ul className="top1-list">{Object.entries(stability.top1_share).map(([name, indicator]) => <li key={name}>
        <span>{name}</span>
        <span className="top1-bar" aria-hidden="true"><i style={{ width: `${Math.round(Math.min(1, indicator.value ?? 0) * 100)}%` }} className={(indicator.value ?? 0) === maxShare ? "is-max" : undefined} /></span>
        <Indicator indicator={indicator} compact />
      </li>)}</ul>
      <Indicator indicator={stability.rank_corr_mean} />
    </div>}
    {stability?.conflicts.length ? <div className="conflict-list" data-testid="conflicts">
      <h4>{t("ranking.conflicts")}</h4>
      <ul>{stability.conflicts.map((conflict, index) => <li key={index}>{english && conflict.text_en ? conflict.text_en : conflict.text_es}</li>)}</ul>
    </div> : null}
    {stability?.interpretation_es && !english && <p>{stability.interpretation_es}</p>}
    <p className="stability-note" data-testid="stability-note">{t("common.stabilityInterpretation")}</p>
  </section>;
}
