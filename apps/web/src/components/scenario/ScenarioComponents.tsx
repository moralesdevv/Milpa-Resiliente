import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";

type ScenarioTag = components["schemas"]["ScenarioTag"];
type AdaptationMode = components["schemas"]["AdaptationMode"];

export function scenarioKey(scenario: ScenarioTag): string {
  return `${scenario.scenario_id}::${scenario.adaptation_mode}`;
}

export function ScenarioBadge({ scenario }: { scenario: ScenarioTag }) {
  const { t } = useTranslation();
  return <section className="scenario-badge" aria-label={t("scenario.badgeLabel")} data-scenario-id={scenario.scenario_id}>
    <div className="scenario-badge__heading">
      <span className="scenario-badge__dot" aria-hidden="true" />
      <strong>{t("common.syntheticScenario")}</strong>
      <span>{scenario.label}</span>
      <code>{scenario.scenario_id}</code>
    </div>
    <dl className="scenario-badge__details">
      <div><dt>{t("scenario.temperature")}</dt><dd>{scenario.delta_t_c} °C</dd></div>
      <div><dt>{t("scenario.precipitationFactor")}</dt><dd>×{scenario.precip_factor}</dd></div>
      <div><dt>{t("scenario.onsetDelay")}</dt><dd>{scenario.onset_delay_days} d</dd></div>
      <div><dt>{t("scenario.humidity")}</dt><dd>{t(`scenario.humidityModes.${scenario.humidity_assumption}`)}</dd></div>
      <div><dt>{t("scenario.adaptation")}</dt><dd>{t(`scenario.adaptationModes.${scenario.adaptation_mode}`)}</dd></div>
    </dl>
    <p className="scenario-badge__method">{scenario.method_doc} · {scenario.engine_version}</p>
    <p className="scenario-badge__footnote">{t("scenario.configurationNote")}</p>
  </section>;
}

export function ScenarioPicker({ scenarios, value, onChange, disabled = false }: {
  scenarios: ScenarioTag[];
  value: string;
  onChange: (scenarioId: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => onChange(event.currentTarget.value);

  return <label className="field">
    <span>{t("scenario.chooseComputed")}</span>
    <select value={value} onChange={handleChange} disabled={disabled || scenarios.length === 0}>
      <option value="">{scenarios.length ? t("scenario.selectOne") : t("scenario.noneComputed")}</option>
      {scenarios.map((scenario) => <option key={scenarioKey(scenario)} value={scenarioKey(scenario)}>
        {scenario.label} · {scenario.scenario_id} · {t(`scenario.adaptationModes.${scenario.adaptation_mode}`)}
      </option>)}
    </select>
    <small>{t("scenario.notComputedHint")}</small>
  </label>;
}

export function AdaptationToggle({ value, onChange, disabled = false }: {
  value: AdaptationMode;
  onChange: (mode: AdaptationMode) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return <fieldset className="segmented-control" disabled={disabled}>
    <legend>{t("scenario.adaptation")}</legend>
    {(["none", "onset_rule"] as const).map((mode) => <label key={mode}>
      <input type="radio" name="adaptation-mode" value={mode} checked={value === mode} onChange={() => onChange(mode)} />
      <span>{t(`scenario.adaptationModes.${mode}`)}</span>
    </label>)}
  </fieldset>;
}
