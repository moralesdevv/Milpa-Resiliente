import type { components } from "../api/types.gen";

type Strategy = components["schemas"]["StrategyRiskDTO"];
type Rank = components["schemas"]["RankResponse"];

export type Family = "Reference" | "Association" | "Rotation" | "Alternative";

/** Strategy family from its explicit change axes (README §11.6: a date or variety change is not a rotation). */
export function strategyFamily(item: Pick<Strategy, "changes_from_reference">): Family {
  const axes = (item.changes_from_reference ?? []) as string[];
  if (axes.length === 0) return "Reference";
  if (axes.includes("rotation")) return "Rotation";
  if (axes.includes("association")) return "Association";
  return "Alternative";
}

type IndicatorLike = { value?: number | null } | undefined;

export function p90Severity(item: Strategy): number | null {
  const water = item.water_inputs as Record<string, IndicatorLike>;
  return water.p90_severity_by_agri_year?.value ?? null;
}

export function criticalPct(item: Strategy): number | null {
  return item.cohort_freq_critical?.value ?? null;
}

const fmt = (value: number, digits = 0) => value.toLocaleString("en-US", { maximumFractionDigits: digits });

export type Insights = { findings: string[]; cautions: string[] };

/**
 * Plain-language reading of what the engine returned. Every sentence is built from a figure the engine
 * produced (or from its absence): nothing is predicted and no criterion is filled in.
 */
export function buildInsights(items: Strategy[], rank: Rank | null | undefined): Insights {
  const findings: string[] = [];
  const cautions: string[] = [];
  if (items.length === 0) return { findings, cautions: ["No strategy results are available for this run and scenario."] };

  const cohorts = Math.max(...items.map((item) => Number((item as { n_independent_cohorts?: number }).n_independent_cohorts ?? 0)));
  findings.push(`${items.length} strategies were evaluated${cohorts ? ` over up to ${cohorts} independent planting cohorts` : ""}, each from the same climate series and the same rules.`);

  const critical = items.filter((item) => (criticalPct(item) ?? 0) > 0);
  if (critical.length === 0) {
    findings.push("No strategy reached the critical threshold in any evaluated cohort. With provisional thresholds this means “not detected”, not “safe”.");
  } else {
    // Sentence format fixed by the product definition: "In X of the N evaluable ..." with X and N from the engine.
    const list = critical.map((item) => {
      const pct = criticalPct(item) ?? 0;
      const n = Number((item as { n_decided?: number }).n_decided ?? 0);
      return n > 0 ? `${item.name}: in ${fmt((pct / 100) * n)} of the ${n} evaluable cohorts (${fmt(pct, 1)} % of cohorts)` : `${item.name} (${fmt(pct, 1)} % of cohorts)`;
    }).join("; ");
    findings.push(`A critical stage fell above the exposure threshold — ${list}.`);
  }

  const withSeverity = items.map((item) => ({ item, p90: p90Severity(item) })).filter((row): row is { item: Strategy; p90: number } => row.p90 !== null);
  if (withSeverity.length > 1) {
    const sorted = [...withSeverity].sort((a, b) => a.p90 - b.p90);
    const low = sorted[0];
    const high = sorted[sorted.length - 1];
    findings.push(`Exposure severity in critical stages (90th percentile) ranges from ${fmt(low.p90)} mm (${low.item.name}) to ${fmt(high.p90)} mm (${high.item.name}). It is an exposure indicator, not a yield or a soil-water deficit.`);
  }

  if (rank && rank.status === "ok" && rank.ranking.length) {
    const first = rank.ranking[0];
    const margin = rank.margin_within_uncertainty;
    const stability = rank.stability?.flag;
    findings.push(`Under equal priorities the order puts ${first.name} first${margin === true ? ", but its lead over the next strategy is within the uncertainty margin" : margin === false ? ", with a lead beyond the uncertainty margin" : ""}. Stability of the order under changed weights: ${stability ?? "unknown"} (it measures sensitivity, not the probability of being best).`);
    const label: Record<string, string> = { water: "water security", soil: "soil health", food: "household food", income: "income" };
    const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 > 10 && n % 100 < 14 ? 0 : Math.min(n % 10, 4) % 4]}`;
    const where = rank.criteria_used.flatMap((criterion) => {
      const values = rank.ranking.map((row) => row.criteria?.[criterion]?.normalised?.value ?? null);
      const mine = first.criteria?.[criterion]?.normalised?.value;
      if (mine === null || mine === undefined) return [];
      const comparable = values.filter((v): v is number => v !== null);
      const position = comparable.filter((v) => v > mine).length + 1;
      const ties = comparable.filter((v) => Math.abs(v - mine) < 1e-9).length - 1;
      return [`${label[criterion] ?? criterion}: ${ordinal(position)} of ${comparable.length}${ties > 0 ? ` (tied with ${ties} other${ties > 1 ? "s" : ""})` : ""}`];
    });
    if (where.length > 1) findings.push(`Where ${first.name} stands on each criterion — ${where.join("; ")}. The water score counts the share of critical cohorts only (severity is shown separately), and the overall order combines the criteria with the chosen priorities.`);
    const used = rank.criteria_used.join(", ");
    cautions.push(`The ranking uses only the criteria with evidence: ${used}. Criteria without evidence are excluded for every strategy, so no strategy wins by having less data.`);
  } else if (rank && rank.status !== "ok") {
    cautions.push("The engine could not rank the strategies with the available criteria (insufficient coverage); the partial table is shown instead.");
  }
  return { findings, cautions };
}
