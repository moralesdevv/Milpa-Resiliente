import { useTranslation } from "react-i18next";

import type { components } from "../../api/types.gen";
import { Empty, InsufficientData } from "../common/states";

type RankData = components["schemas"]["RankResponse"];

/**
 * Compares the order of two ranking responses (BASE and the chosen scenario).
 * Only positions are compared; no new score is computed here.
 */
export function PositionInversions({ base, selected }: { base: RankData | null | undefined; selected: RankData | null | undefined }) {
  const { t } = useTranslation();
  if (!base || !selected) return <Empty title={t("ranking.inversionsEmpty")} detail={t("ranking.inversionsNeedBoth")} />;
  if (base.status !== "ok" || selected.status !== "ok") return <InsufficientData detail={t("ranking.inversionsInsufficient")} />;

  const basePosition = new Map(base.ranking.map((row, index) => [row.strategy_version_id, index + 1]));
  const rows = selected.ranking.map((row, index) => {
    const before = basePosition.get(row.strategy_version_id);
    const after = index + 1;
    return { id: row.strategy_version_id, name: row.name, before, after, change: before === undefined ? "new" : before === after ? "same" : before > after ? "up" : "down" };
  });
  const changed = rows.some((row) => row.change === "up" || row.change === "down");

  return <section aria-labelledby="inversions-title" data-testid="inversions">
    <h3 id="inversions-title">{t("ranking.inversions")}</h3>
    <p className={changed ? "notice" : "chart-caption"}>{changed ? t("ranking.inversionsFound") : t("ranking.inversionsNone")}</p>
    <div className="table-scroll"><table className="data-table">
      <thead><tr><th>{t("forms.strategyId")}</th><th>{t("ranking.positionBase")}</th><th>{t("ranking.positionScenario")}</th><th>{t("ranking.change")}</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.id} data-change={row.change}>
        <th scope="row">{row.name}</th><td>{row.before ?? "—"}</td><td>{row.after}</td>
        <td><span aria-hidden="true">{row.change === "up" ? "▲ " : row.change === "down" ? "▼ " : row.change === "same" ? "= " : ""}</span>{t(`ranking.changes.${row.change}`)}</td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}
