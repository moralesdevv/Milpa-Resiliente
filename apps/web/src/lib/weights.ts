import type { components } from "../api/types.gen";

export type Criterion = components["schemas"]["Criterion"];
export type Weights = components["schemas"]["Weights"];

export const criteria: Criterion[] = ["water", "soil", "food", "income"];

/**
 * Moves one weight and rescales the others proportionally so the four always
 * add up to 1 (two decimals). This is input handling, not scientific logic.
 */
export function rebalance(weights: Weights, changed: Criterion, nextValue: number): Weights {
  const value = Math.min(1, Math.max(0, Math.round(nextValue * 100) / 100));
  const others = criteria.filter((criterion) => criterion !== changed);
  const remaining = Math.round((1 - value) * 100) / 100;
  const otherSum = others.reduce((sum, criterion) => sum + weights[criterion], 0);
  const next = { ...weights, [changed]: value } as Weights;
  let assigned = 0;
  others.forEach((criterion, index) => {
    const share = otherSum > 0 ? weights[criterion] / otherSum : 1 / others.length;
    const scaled = index === others.length - 1
      ? Math.round((remaining - assigned) * 100) / 100
      : Math.round(share * remaining * 100) / 100;
    next[criterion] = Math.max(0, scaled);
    assigned += next[criterion];
  });
  return next;
}
