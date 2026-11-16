/**
 * Shared presentation tokens for the ECharts panels. Colours mirror the CSS tokens in styles.css
 * (kept in sync by hand: ECharts renders to canvas and cannot read CSS variables).
 * Only presentation lives here; data, series and meaning stay in each chart component.
 */
export const chartColors = {
  /** Precipitation / effective precipitation: atmospheric blue (4.9:1 on white). */
  water: "#0b659f",
  /** Crop demand / reference evapotranspiration: maize ochre (3.9:1 on white, ≥3:1 for graphics). */
  demand: "#a56b00",
  /** Exposure and risk: clay red, never reused for brand. */
  risk: "#b8321f",
  ink: "#14261e",
  muted: "#3f5248",
  grid: "#e6dfc9",
  axis: "#6d7f73",
  criticalBand: "rgba(184, 50, 31, 0.10)",
  neutralBand: "rgba(11, 101, 159, 0.08)",
  /** Categorical series (strategies): distinguishable in colour and, via aria decals, in pattern. */
  series: ["#067a52", "#0b659f", "#a56b00", "#b8501f", "#4d6056"],
} as const;

export const chartFont = "'Atkinson Hyperlegible Next', 'Segoe UI', system-ui, sans-serif";

export const baseTextStyle = { fontFamily: chartFont, color: chartColors.ink, fontSize: 12 } as const;

export const axisStyle = {
  axisLine: { lineStyle: { color: chartColors.axis } },
  axisTick: { lineStyle: { color: chartColors.axis } },
  axisLabel: { color: chartColors.muted, fontFamily: chartFont, fontSize: 12 },
  nameTextStyle: { color: chartColors.muted, fontFamily: chartFont, fontSize: 12, fontWeight: 600 },
} as const;

export const valueAxisStyle = {
  ...axisStyle,
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { lineStyle: { color: chartColors.grid, type: "solid" as const } },
} as const;

export const legendStyle = {
  top: 0,
  icon: "roundRect",
  itemWidth: 14,
  itemHeight: 8,
  itemGap: 20,
  textStyle: { color: chartColors.ink, fontFamily: chartFont, fontSize: 12.5 },
} as const;

/**
 * Entrada y transición de los gráficos: aparición progresiva y cambio suave entre datos.
 * Se desactiva con prefers-reduced-motion. Solo presentación: no altera series ni escalas.
 */
export function chartMotion() {
  const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return { animation: false } as const;
  return {
    animation: true,
    animationDuration: 760,
    animationEasing: "cubicOut",
    animationDelay: (index: number) => index * 28,
    animationDurationUpdate: 420,
    animationEasingUpdate: "cubicInOut",
  } as const;
}
