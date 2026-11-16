import { describe, expect, it } from "vitest";

import { buildInsights, strategyFamily } from "./insights";

const ind = (value: number) => ({ value }) as never;
const strategy = (name: string, axes: string[], critical: number, p90: number) => ({
  name,
  changes_from_reference: axes,
  cohort_freq_critical: ind(critical),
  water_inputs: { p90_severity_by_agri_year: ind(p90) },
  n_independent_cohorts: 25,
}) as never;

describe("strategyFamily", () => {
  it("separates reference, association, rotation and alternatives (a date change is not a rotation)", () => {
    expect(strategyFamily({ changes_from_reference: [] })).toBe("Reference");
    expect(strategyFamily({ changes_from_reference: ["association"] as never })).toBe("Association");
    expect(strategyFamily({ changes_from_reference: ["rotation"] as never })).toBe("Rotation");
    expect(strategyFamily({ changes_from_reference: ["planting_date"] as never })).toBe("Alternative");
  });
});

describe("buildInsights", () => {
  it("never calls zero critical cohorts 'safe' and reports the severity range from engine figures", () => {
    const out = buildInsights([strategy("A", [], 0, 80), strategy("B", ["rotation"], 0, 150)], null);
    const text = out.findings.join(" ");
    expect(text).toContain("not detected");
    expect(text).toContain("not “safe”");
    expect(text).toContain("80 mm (A)");
    expect(text).toContain("150 mm (B)");
    expect(text).not.toMatch(/forecast|predict|yield will/i);
  });

  it("names strategies with critical exposure and explains the ranking only over evidenced criteria", () => {
    const rank = { status: "ok", ranking: [{ name: "B" }], margin_within_uncertainty: true, stability: { flag: "stable" }, criteria_used: ["water", "soil"] } as never;
    const out = buildInsights([strategy("A", [], 4, 80), strategy("B", [], 0, 90)], rank);
    expect(out.findings.join(" ")).toContain("A (4 % of cohorts)");
    expect(out.findings.join(" ")).toContain("above the exposure threshold");
    expect(out.findings.join(" ")).toContain("within the uncertainty margin");
    expect(out.cautions.join(" ")).toContain("water, soil");
  });

  it("explains that the leader can lead on a criterion other than water", () => {
    const row = (name: string, water: number, soil: number) => ({ name, criteria: { water: { normalised: ind(water) }, soil: { normalised: ind(soil) } } });
    const rank = { status: "ok", ranking: [row("B", 0, 1), row("A", 1, 0)], margin_within_uncertainty: false, stability: { flag: "stable" }, criteria_used: ["water", "soil"] } as never;
    const text = buildInsights([strategy("A", [], 0, 80), strategy("B", [], 0, 90)], rank).findings.join(" ");
    expect(text).toContain("water security: 2nd of 2");
    expect(text).toContain("soil health: 1st of 2");
  });

  it("handles an empty run", () => {
    expect(buildInsights([], null).findings).toHaveLength(0);
  });
});
