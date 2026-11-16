import { describe, expect, it } from "vitest";

import gridIds from "./grid-ids.fixture.json";
import { buildScenarioId } from "./ScenarioLauncher";

/** The selectors may only ever produce ids that exist in the engine's standard grid (milpa_core.standard_grid). */
describe("scenario id builder", () => {
  it("reproduces the engine's standard grid exactly (44 non-BASE ids)", () => {
    const built = new Set<string>();
    for (const dt of [0, 1, 2]) for (const p of [0, -10, -20]) for (const d of [0, 10, 20]) for (const h of ["rh", "ea"] as const) {
      built.add(buildScenarioId(dt, p, d, h));
    }
    built.delete("T+0_P+0_D+0_Hna"); // that combination is the BASE run, which the launcher refuses to recompute
    expect([...built].sort()).toEqual(gridIds);
    expect(gridIds).toHaveLength(44);
  });

  it("drops the humidity assumption when the temperature does not change", () => {
    expect(buildScenarioId(0, -10, 10, "ea")).toBe("T+0_P-10_D+10_Hna");
    expect(buildScenarioId(2, -20, 20, "rh")).toBe("T+2_P-20_D+20_Hrh");
  });
});
