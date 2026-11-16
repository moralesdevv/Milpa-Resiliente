import { useTranslation } from "react-i18next";

import { useStrategyCatalog, useStrategyVersion } from "../../api/queries";
import type { components } from "../../api/types.gen";
import { Empty, ErrorState, Loading } from "../common/states";

type Strategy = components["schemas"]["StrategyOut"];

function StrategyCycles({ strategy }: { strategy: Strategy }) {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  const version = useStrategyVersion(strategy.strategy_id, strategy.latest_version);
  if (strategy.latest_version == null) return <p className="chart-caption">{t("strategy.noVersion", "Sin versión publicada")}</p>;
  if (version.isLoading) return <Loading />;
  if (version.isError) return <ErrorState error={version.error} onRetry={() => void version.refetch()} />;
  return <ol>{(version.data?.cycles ?? []).map((cycle) => {
    const crops = cycle.components.map((component) => (english ? component.crop_name_en : component.crop_name_es) ?? component.crop_code ?? component.variety_id);
    const window = cycle.plant_window_start ? ` · ${cycle.plant_window_start}${cycle.plant_window_end ? `–${cycle.plant_window_end}` : ""}` : "";
    return <li key={cycle.cycle_idx}>{t("calendar.cycle")} {cycle.cycle_idx}: {crops.join(" + ")} · {cycle.season}{window}</li>;
  })}</ol>;
}

/** Catalog of versioned strategies, each with its explicit change axes and its cycles. */
export type RunStrategy = { id: string; name: string; changes: string[]; horizonYears: number; cycles: { idx: number; crop: string }[] };

/** Used when the versioned catalog (R1) is empty: the strategies the engine actually evaluated in this run. */
function RunStrategies({ strategies }: { strategies: RunStrategy[] }) {
  return <ul className="strategy-catalog" data-testid="strategy-catalog-run">
    {strategies.map((strategy) => <li key={strategy.id} className="strategy-catalog__item">
      <h3>{strategy.name}</h3>
      <p className="strategy-catalog__axes">{strategy.changes.length === 0 ? "Reference strategy" : `Changes from the reference: ${strategy.changes.join(", ")}`} · horizon {strategy.horizonYears} yr</p>
      <ol>{strategy.cycles.map((cycle) => <li key={cycle.idx}>Cycle {cycle.idx}: {cycle.crop}</li>)}</ol>
    </li>)}
  </ul>;
}

export function StrategyCatalog({ runStrategies = [] }: { runStrategies?: RunStrategy[] }) {
  const { t } = useTranslation();
  const catalog = useStrategyCatalog();
  if (catalog.isLoading) return <Loading />;
  if (catalog.isError) return <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />;
  if (!catalog.data?.length && runStrategies.length) return <RunStrategies strategies={runStrategies} />;
  if (!catalog.data?.length) return <Empty title={t("strategy.catalogEmpty")} detail={t("strategy.catalogEmptyDetail")} />;

  return <ul className="strategy-catalog" data-testid="strategy-catalog">
    {catalog.data.map((strategy) => <li key={strategy.strategy_id} className="strategy-catalog__item">
      <h3>{strategy.name}</h3>
      <p className="strategy-catalog__axes">
        {strategy.is_reference || strategy.changes_from_reference.length === 0
          ? t("strategy.isReference")
          : `${t("strategy.changesFrom")}: ${strategy.changes_from_reference.map((axis) => t(`strategy.axes.${axis}`)).join(", ")}`}
      </p>
      <StrategyCycles strategy={strategy} />
    </li>)}
  </ul>;
}
