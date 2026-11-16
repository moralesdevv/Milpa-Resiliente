import { describe, expect, it } from "vitest";

import { criteria, rebalance } from "./weights";
import type { Weights } from "./weights";

const sum = (weights: Weights) => criteria.reduce((total, criterion) => total + weights[criterion], 0);

describe("rebalance (T-P06 en la entrada de la interfaz)", () => {
  it("keeps the four weights adding up to 1 after any slider move", () => {
    const start: Weights = { water: 0.25, soil: 0.25, food: 0.25, income: 0.25 };
    for (const criterion of criteria) {
      for (const value of [0, 0.05, 0.33, 0.5, 0.9, 1]) {
        const next = rebalance(start, criterion, value);
        expect(Math.abs(sum(next) - 1)).toBeLessThan(1e-9);
        for (const item of criteria) expect(next[item]).toBeGreaterThanOrEqual(0);
        expect(next[criterion]).toBeCloseTo(value, 2);
      }
    }
  });

  it("spreads the remainder evenly when the other weights were all zero", () => {
    const next = rebalance({ water: 1, soil: 0, food: 0, income: 0 }, "water", 0.4);
    expect(next).toEqual({ water: 0.4, soil: 0.2, food: 0.2, income: 0.2 });
  });

  it("scales the others in proportion", () => {
    const next = rebalance({ water: 0.4, soil: 0.4, food: 0.1, income: 0.1 }, "water", 0.2);
    expect(next.soil).toBeGreaterThan(next.food);
    // 0.8 sobrante repartido 4:1:1 entre suelo, alimentación e ingreso → 0.53 / 0.13 / 0.14 (el último absorbe el redondeo)
    expect(next.soil).toBeCloseTo(0.53, 2);
    expect(sum(next)).toBeCloseTo(1, 9);
  });
});
