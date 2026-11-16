/**
 * FIXTURE SINTÉTICO DE PRUEBA (R4).
 *
 * Todo valor de este archivo está inventado para ejercitar la interfaz y las
 * pruebas de aceptación. No representa una zona, un suelo ni un resultado real,
 * no proviene de R1/R2 y no debe usarse para decisiones. Cada indicador sale
 * marcado como provisional y con evidencia C.
 */
import { createHash } from "node:crypto";

import type { components } from "./draft.gen";

type S = components["schemas"];

export const ZONE_ID = "00000000-0000-4000-8000-000000000001";
export const REGION_ID = "00000000-0000-4000-8000-000000000002";
export const RUN_ID = "run-synthetic-0001";
export const RUN_NO_MATRIX_ID = "run-synthetic-nomatrix";
export const PARCEL_ID = "parcel-synthetic-001";
export const FIXTURE_NOTE = "Fixture sintético de prueba, no representa un suelo ni una zona real.";

export const STRATEGY_REF = "strategy-milpa-reference";
export const STRATEGY_EARLY = "strategy-milpa-early-planting";
export const STRATEGY_ROT = "strategy-rotation-two-years";

export const BASE = "BASE";
export const COMBINED = "T+2_P-20_D+20_Hrh";
export const COMBINED_ALT = "T+2_P-20_D+20_Hea";

export const sha = (text: string) => createHash("sha256").update(text).digest("hex");

function provenance(): S["ProvenanceInfo"] {
  return {
    provenance: "modelado",
    evidence: "C",
    evidence_rule: "R-SYNTHETIC-FIXTURE",
    sources: [{
      code: "SYNTHETIC",
      product_name: "Fixture sintético de prueba R4",
      institution: "Equipo R4 (no es una institución científica)",
      is_nasa: false,
      version: "fixture-1",
      citation: null,
      url: null,
    }],
    dataset_version: "fixture-1",
    period: { start: "2001-01-01", end: "2025-12-31" },
    spatial_res: null,
    temporal_res: "decena",
    method: "Valor estático de fixture; no es un cálculo",
    retrieved_at: null,
    assumptions: ["Valores inventados solo para probar la interfaz."],
    limitations: [FIXTURE_NOTE],
    run_id: RUN_ID,
  };
}

export function ind(code: string, es: string, en: string, value: number | null, unit: string, kind: S["IndicatorKind"] = "criterion"): S["IndicatorNumber"] {
  return {
    code,
    label_es: es,
    label_en: en,
    value,
    unit,
    kind,
    label: kind === "exposure" ? "indicador_exposicion_climatica" : null,
    provisional: true,
    reason: FIXTURE_NOTE,
    provenance: provenance(),
    scenario: null,
  };
}

export const scenarioTag = (id: string, adaptation: S["AdaptationMode"] = "none"): S["ScenarioTag"] => {
  const isBase = id === BASE;
  const delay = id.includes("D+20") ? 20 : 0;
  return {
    scenario_id: id,
    label: "escenario sintético",
    delta_t_c: ind("scenario.delta_t_c", "Cambio de temperatura", "Temperature change", id.includes("T+2") ? 2 : 0, "°C", "climate_input"),
    precip_factor: ind("scenario.precip_factor", "Factor de precipitación", "Precipitation factor", id.includes("P-20") ? 0.8 : 1, "×", "climate_input"),
    onset_delay_days: ind("scenario.onset_delay_days", "Retraso del inicio de lluvias", "Rainy-season onset delay", delay, "días", "climate_input") as S["IndicatorInteger"],
    humidity_assumption: isBase ? "not_applicable" : id.endsWith("Hea") ? "constant_ea" : "constant_rh",
    adaptation_mode: adaptation,
    method_doc: "docs/METHODS.md §19 (fixture)",
    engine_version: "fixture-1",
    executed_at: "2026-11-14T00:00:00Z",
  };
};

export const STRATEGIES = [
  { id: STRATEGY_REF, name: "Milpa tradicional (referencia)", cycles: 1, water: { BASE: 0.85, SCEN: 0.6 }, soil: 0.5, food: 0.7 as number | null, income: 0.5, freq: { BASE: 0.28, SCEN: 0.52 } },
  { id: STRATEGY_EARLY, name: "Milpa con siembra adelantada", cycles: 1, water: { BASE: 0.75, SCEN: 0.55 }, soil: 0.5, food: 0.7 as number | null, income: 0.5, freq: { BASE: 0.2, SCEN: 0.44 } },
  { id: STRATEGY_ROT, name: "Rotación de dos años (maíz y frijol)", cycles: 2, water: { BASE: 0.6, SCEN: 0.62 }, soil: 0.65, food: null as number | null, income: 0.6, freq: { BASE: 0.32, SCEN: 0.4 } },
] as const;

export const strategyCatalog = (): S["PageStrategyCatalogItem"] => ({
  items: [
    { strategy_version_id: STRATEGY_REF, name: STRATEGIES[0].name, is_reference: true, changes_from_reference: [], cycles: [{ cycle_idx: 0, crops: ["maíz", "frijol"], season: "primera", planting_window: "mayo–junio" }] },
    { strategy_version_id: STRATEGY_EARLY, name: STRATEGIES[1].name, changes_from_reference: ["planting_date"], cycles: [{ cycle_idx: 0, crops: ["maíz", "frijol"], season: "primera", planting_window: "mayo (adelantada)" }] },
    { strategy_version_id: STRATEGY_ROT, name: STRATEGIES[2].name, changes_from_reference: ["rotation"], cycles: [{ cycle_idx: 0, crops: ["maíz"], season: "primera", planting_window: "mayo–junio" }, { cycle_idx: 1, crops: ["frijol"], season: "postrera", planting_window: "agosto" }] },
  ],
  next_cursor: null,
});

export const zoneDetail = (): S["ZoneDTO"] => ({
  zone_id: ZONE_ID,
  region_id: REGION_ID,
  name: "ZONA SINTÉTICA · fixture de prueba",
  elevation_m: ind("zone.elevation_m", "Elevación", "Elevation", 480, "m", "climate_input"),
  slope_pct: ind("zone.slope_pct", "Pendiente", "Slope", 12, "%", "climate_input"),
  sources: [
    { code: "POWER", product_name: "NASA POWER diario (descripción)", institution: "NASA", is_nasa: true, version: null, citation: null, url: null },
    { code: "IMERG", product_name: "GPM IMERG Final V07 (descripción)", institution: "NASA (GES DISC)", is_nasa: true, version: null, citation: null, url: null },
    { code: "SOILGRIDS", product_name: "SoilGrids 2.0 (descripción)", institution: "ISRIC", is_nasa: false, version: null, citation: null, url: null },
    { code: "DEM", product_name: "Copernicus GLO-30 (descripción)", institution: "ESA (no es NASA)", is_nasa: false, version: null, citation: null, url: null },
  ],
  context: {
    synthetic_fixture: true,
    message: FIXTURE_NOTE,
    cells: [
      { cell_id: "imerg-0.1deg", source: "IMERG", weight: ind("cell.weight.imerg", "Peso de la celda IMERG", "IMERG cell weight", 0.7, "", "climate_input"), south: 14.8, west: -89.4, north: 14.9, east: -89.3 },
      { cell_id: "power-0.5deg", source: "POWER", weight: ind("cell.weight.power", "Peso de la celda POWER", "POWER cell weight", 0.3, "", "climate_input"), south: 14.5, west: -89.625, north: 15, east: -89 },
    ],
    crops: [
      { code: "maiz", name_es: "Maíz", name_en: "Maize", seasons: ["primera"], calendar_validated: false },
      { code: "frijol", name_es: "Frijol", name_en: "Common bean", seasons: ["primera", "postrera"], calendar_validated: false },
    ],
    pending: ["DP-01 zona piloto", "DP-02 cultivos y variedades locales", "DP-03 calendarios agrícolas validados"],
  },
});

export const dataQuality = (): S["DataQualityDTO"] => ({
  synthetic_fixture: true,
  coverage: ["precip", "tmax", "tmin", "srad"].flatMap((variable) => [2001, 2012, 2025].map((year) => ({
    variable,
    year,
    missing_pct: ind(`quality.missing.${variable}.${year}`, "Faltantes", "Missing", variable === "srad" && year === 2012 ? 4 : 0, "%", "climate_input"),
  }))),
  comparisons: [
    { pair: "IMERG vs POWER", bias: ind("quality.bias.imerg_power", "Sesgo", "Bias", -6, "%", "climate_input"), correlation: ind("quality.corr.imerg_power", "Correlación", "Correlation", 0.82, "", "climate_input") },
    { pair: "IMERG vs estación", bias: ind("quality.bias.imerg_station", "Sesgo", "Bias", 0, "%", "climate_input"), correlation: ind("quality.corr.imerg_station", "Correlación", "Correlation", null, "", "climate_input") },
  ],
  ea_sensitivity: ind("quality.ea_sensitivity", "Diferencia de ET0 entre rutas de ea", "ET0 difference between ea routes", 3, "%", "climate_input"),
  sources: zoneDetail().sources,
});

export const climateHistory = (): S["ClimateHistoryDTO"] => ({
  synthetic_fixture: true,
  years: Array.from({ length: 25 }, (_, i) => ({
    year: 2001 + i,
    precip_mm: ind(`history.precip.${2001 + i}`, "Precipitación anual", "Annual precipitation", 900 + ((i * 53) % 240), "mm", "climate_input"),
    et0_mm: ind(`history.et0.${2001 + i}`, "ET0 anual", "Annual ET0", 1400 + ((i * 31) % 120), "mm", "climate_input"),
    n_valid_days: ind(`history.valid.${2001 + i}`, "Días válidos", "Valid days", 365, "días", "climate_input") as S["IndicatorInteger"],
  })),
  trends: [
    { variable: "precip", change_per_decade: ind("trend.precip", "Cambio de lluvia por década", "Rainfall change per decade", -12, "mm", "climate_input"), description_es: "Tendencia descriptiva del fixture; no es una prueba estadística." },
  ],
  provenance: provenance(),
});

const scenarioKeyOf = (id: string) => (id === BASE ? "BASE" : "SCEN") as "BASE" | "SCEN";

export function summary(scenario: string): S["PageStrategyRiskDTO"] {
  const k = scenarioKeyOf(scenario);
  const cycleRisk = (strategy: (typeof STRATEGIES)[number], cycleIdx: number, variety: string): S["CycleRiskDTO"] => {
    const f = Math.min(0.95, strategy.freq[k] + cycleIdx * 0.05);
    const id = `${strategy.id}.${cycleIdx}.${variety}`;
    const mk = (suffix: string, es: string, en: string, v: number, unit: string, kind: S["IndicatorKind"] = "exposure") => ind(`${id}.${suffix}`, es, en, v, unit, kind);
    return {
      strategy_version_id: strategy.id,
      cycle_idx: cycleIdx,
      variety_id: variety,
      freq_critical: mk("freq", "Frecuencia crítica", "Critical frequency", Number((f * 100).toFixed(0)), "%"),
      severity_median: mk("sev50", "Severidad mediana", "Median severity", Math.round(20 + f * 60), "mm"),
      severity_p90: mk("sev90", "Severidad P90", "P90 severity", Math.round(40 + f * 110), "mm"),
      severity_cvar90: mk("cvar90", "CVaR90", "CVaR90", Math.round(55 + f * 140), "mm"),
      worst_year: mk("worst", "Peor año", "Worst year", 2009 + cycleIdx, "año") as S["IndicatorInteger"],
      worst_year_severity: mk("worstsev", "Severidad del peor año", "Worst-year severity", Math.round(80 + f * 150), "mm"),
      coverage: {
        n_valid: mk("nvalid", "Años válidos", "Valid years", 24, "años", "climate_input") as S["IndicatorInteger"],
        n_expected: mk("nexp", "Años esperados", "Expected years", 25, "años", "climate_input") as S["IndicatorInteger"],
        n_decided: mk("ndec", "Años decididos", "Decided years", 23, "años", "climate_input") as S["IndicatorInteger"],
        missing_pct: mk("miss", "Faltantes", "Missing", 4, "%", "climate_input"),
      },
      threshold_sensitivity: {
        low: mk("thr.low", "Frecuencia con umbral bajo", "Frequency, low threshold", Math.max(0, Math.round(f * 100) - 8), "%"),
        central: mk("thr.mid", "Frecuencia con umbral central", "Frequency, central threshold", Math.round(f * 100), "%"),
        high: mk("thr.high", "Frecuencia con umbral alto", "Frequency, high threshold", Math.round(f * 100) + 8, "%"),
      },
      peff_sensitivity: strategy.id === STRATEGY_ROT && cycleIdx === 1
        ? {
          usda_scs_fao: mk("peff.usda", "Frecuencia con Pef USDA-SCS", "Frequency with USDA-SCS Pef", Math.round(f * 100), "%"),
          fao_dependable: mk("peff.fao", "Frecuencia con Pef FAO dependable", "Frequency with FAO dependable Pef", Math.round(f * 100) + 14, "%"),
        }
        : {},
      flags: strategy.id === STRATEGY_ROT && cycleIdx === 1 ? ["peff_sensible_al_metodo"] : [],
    };
  };
  return {
    items: STRATEGIES.map((strategy) => {
      const by_cycle: S["CycleRiskDTO"][] = [];
      for (let c = 0; c < strategy.cycles; c++) {
        by_cycle.push(cycleRisk(strategy, c, "variety-a"));
        if (strategy.id === STRATEGY_REF) by_cycle.push(cycleRisk(strategy, c, "variety-b"));
      }
      return {
        strategy_version_id: strategy.id,
        name: strategy.name,
        changes_from_reference: strategy.id === STRATEGY_REF ? [] : strategy.id === STRATEGY_EARLY ? ["planting_date"] : ["rotation"],
        horizon_years: strategy.cycles === 2 ? 2 : 1,
        overlapping_cohorts: strategy.cycles === 2,
        cohort_freq_critical: ind(`${strategy.id}.cohort_freq`, "Frecuencia crítica de cohorte", "Cohort critical frequency", Math.round(strategy.freq[k] * 100), "%", "exposure"),
        water_inputs: {},
        by_cycle,
        consistency: strategy.freq[k] > 0.45 ? "fallos_en_años_desfavorables" : strategy.id === STRATEGY_ROT ? "variable" : "consistente",
      };
    }),
    next_cursor: null,
  };
}

export function heatmap(view: "cycle" | "strategy", strategy: string, cycle: number | null, scenario: string, adaptation: S["AdaptationMode"]): S["HeatmapDTO"] {
  const years = Array.from({ length: 25 }, (_, i) => 2001 + i);
  const plant_md = ["05-15", "05-25", "06-05", "06-15", "06-25"];
  const shift = scenario === BASE ? 0 : 1;
  const state: S["CellState"][][] = years.map((year, yi) => plant_md.map((_, di) => {
    const n = (yi * 7 + di * 3 + shift * 2) % 11;
    if (year === 2003 && di === 0) return "not_evaluable";
    if (n === 0) return "insufficient_data";
    return n % 3 === 0 ? "critical" : "non_critical";
  }));
  const severity = state.map((row, yi) => row.map((cell, di) => cell === "critical"
    ? ind(`heat.${strategy}.${years[yi]}.${plant_md[di]}`, "Severidad", "Severity", 30 + ((yi * 11 + di * 5) % 70), "mm", "exposure")
    : null));
  const pct = plant_md.map((_, di) => {
    const decided = state.filter((row) => row[di] === "critical" || row[di] === "non_critical").length;
    const critical = state.filter((row) => row[di] === "critical").length;
    return decided ? Math.round((critical / decided) * 100) : null;
  });
  const decided = plant_md.map((_, di) => state.filter((row) => row[di] === "critical" || row[di] === "non_critical").length);
  return {
    view,
    strategy_version_id: strategy,
    cycle_idx: view === "cycle" ? cycle ?? 0 : null,
    variety_id: null,
    scenario: scenarioTag(scenario, adaptation),
    mode: "exposure",
    label: "indicador_exposicion_climatica",
    plant_md,
    years,
    state,
    severity,
    pct_critical_by_date: pct.map((v, i) => (v === null ? null : ind(`heat.pct.${i}`, "Porcentaje crítico", "Critical share", v, "%", "exposure"))),
    n_decided_by_date: decided.map((v, i) => ind(`heat.n.${i}`, "Observaciones decididas", "Decided observations", v, "años", "climate_input") as S["IndicatorInteger"]),
    aggregation_rule: view === "strategy" ? "any/sum: una cohorte es crítica si algún ciclo lo es; la severidad suma los ciclos" : null,
    thresholds_used: [{ stage: "floración", value: 25, unit: "mm", peff_method: "usda_scs_fao", citation: null, provisional: true }],
    consistent_window: { start_md: "05-25", end_md: "06-05" },
    provenance: provenance(),
  };
}

export function dekadChart(strategy: string, cohortYear: number, cycle: number, plantDate: string, scenario: string, adaptation: S["AdaptationMode"] = "none"): S["DekadChartDTO"] {
  const dry = scenario === BASE ? 6 : 5;
  const dekads = Array.from({ length: 12 }, (_, i) => {
    const start = new Date(Date.UTC(cohortYear, 4, 11 + i * 10));
    const end = new Date(Date.UTC(cohortYear, 4, 20 + i * 10));
    const pef = i === dry ? 4 : 38 + ((i * 7 + cohortYear) % 17);
    const etc = 22 + Math.min(i, 6) * 3;
    const exposure = Math.max(0, etc - pef);
    return {
      idx: i + 1,
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
      pef_mm: ind(`dk.pef.${i}`, "Precipitación efectiva", "Effective precipitation", pef, "mm", "climate_input"),
      etc_mm: ind(`dk.etc.${i}`, "Demanda del cultivo", "Crop demand", etc, "mm", "climate_input"),
      exposure_mm: ind(`dk.exp.${i}`, "Exposición", "Exposure", exposure, "mm", "exposure"),
      critical_stage: i >= 5 && i <= 7 ? "floración" : i >= 8 && i <= 10 ? "llenado de grano" : null,
      over_threshold: exposure > 20,
    };
  });
  let pc = 0;
  let ec = 0;
  const cumulative = dekads.map((d) => {
    pc += d.pef_mm.value ?? 0;
    ec += d.etc_mm.value ?? 0;
    return {
      idx: d.idx,
      pef_cum_mm: ind(`dk.cumpef.${d.idx}`, "Pef acumulada", "Cumulative Pef", pc, "mm", "climate_input"),
      etc_cum_mm: ind(`dk.cumetc.${d.idx}`, "ETc acumulada", "Cumulative ETc", ec, "mm", "climate_input"),
    };
  });
  return {
    strategy_version_id: strategy,
    cohort_year: cohortYear,
    cycle_idx: cycle,
    plant_date: `${cohortYear}-${plantDate}`,
    scenario: scenarioTag(scenario, adaptation),
    dekads,
    stage_bands: [
      { stage: "floración", start: dekads[5].start, end: dekads[7].end, critical: true },
      { stage: "llenado de grano", start: dekads[8].start, end: dekads[10].end, critical: true },
    ],
    etc_system_exploratory: strategy === STRATEGY_REF ? dekads.map((d, i) => ind(`dk.sys.${i}`, "ETc del sistema (exploratoria)", "System ETc (exploratory)", (d.etc_mm.value ?? 0) * 1.1, "mm", "climate_input")) : null,
    cumulative,
    provenance: { pef: provenance(), etc: provenance(), p_observed: provenance() },
  };
}

type Weights = S["Weights"];
const CRITERIA: S["Criterion"][] = ["water", "soil", "food", "income"];

function score(strategy: (typeof STRATEGIES)[number], criterion: S["Criterion"], scenario: string): number | null {
  if (criterion === "water") return strategy.water[scenarioKeyOf(scenario)];
  return strategy[criterion];
}

/** Pseudo-random but deterministic weight vectors used only by the mock to emulate stability. */
function sampleWeights(n: number, seed: number): number[][] {
  let x = seed || 1;
  const rand = () => {
    x = (x * 1664525 + 1013904223) % 4294967296;
    return x / 4294967296;
  };
  return Array.from({ length: n }, () => {
    const raw = CRITERIA.map(() => -Math.log(1 - rand() + 1e-9));
    const sum = raw.reduce((a, b) => a + b, 0);
    return raw.map((v) => v / sum);
  });
}

export function rank(scenario: string, adaptation: S["AdaptationMode"], weights: Weights, seed = 1): S["RankResponse"] {
  const wArr = CRITERIA.map((c) => weights[c]);
  const used = CRITERIA.filter((c) => STRATEGIES.every((s) => score(s, c, scenario) !== null));
  const excluded = CRITERIA.filter((c) => !used.includes(c));
  const totalW = wArr.reduce((a, b) => a + b, 0) || 1;
  const usedW = used.reduce((a, c) => a + weights[c], 0);
  const coverage = usedW / totalW;
  const decision_log: S["Decision"][] = excluded.map((c) => ({
    kind: "criterion_excluded" as const,
    criterion: c,
    message_es: `El criterio «${c}» no tiene datos para todas las estrategias y se excluyó para todas (soporte común).`,
    message_en: `Criterion "${c}" lacks data for some strategies and was excluded for all (common support).`,
  }));
  const evidence = "C" as const;
  const common = { ranking_id: `ranking-${scenario}-${seed}`, criteria_used: used, weights, evidence, provisional: true, explanations: [] as S["PairExplanation"][] };

  if (coverage < 0.5 || used.length === 0) {
    return {
      ...common,
      status: "insufficient",
      weights_effective: null,
      weight_coverage: ind("rank.weight_coverage", "Cobertura de pesos", "Weight coverage", Math.round(coverage * 100) / 100, "", "ranking"),
      ranking: [],
      partial_table: STRATEGIES.map((s) => ({
        strategy_version_id: s.id,
        name: s.name,
        values: Object.fromEntries(used.map((c) => [c, ind(`partial.${s.id}.${c}`, c, c, score(s, c, scenario), "0–1", "criterion")])),
        reason: "La cobertura de pesos está bajo el mínimo; no se declara un orden.",
      })),
      top_margin: null,
      margin_within_uncertainty: null,
      decision_log: [...decision_log, { kind: "other", criterion: null, message_es: "Cobertura de pesos bajo el mínimo.", message_en: "Weight coverage below the minimum." }],
      stability: { flag: "insufficient", top1_share: {}, rank_corr_mean: ind("stab.corr", "Correlación media de órdenes", "Mean rank correlation", null, "", "ranking"), conflicts: [], interpretation_es: "Mide sensibilidad a los pesos, no la probabilidad de ser la mejor." },
    };
  }

  const totals = STRATEGIES.map((s) => ({ s, total: used.reduce((a, c) => a + (weights[c] / usedW) * (score(s, c, scenario) ?? 0), 0) }));
  const ordered = [...totals].sort((a, b) => b.total - a.total);
  const wins: Record<string, number> = {};
  for (const sample of sampleWeights(300, seed)) {
    const sw = used.reduce((a, c) => a + sample[CRITERIA.indexOf(c)], 0);
    let best = "";
    let bestV = -1;
    for (const s of STRATEGIES) {
      const v = used.reduce((a, c) => a + (sample[CRITERIA.indexOf(c)] / sw) * (score(s, c, scenario) ?? 0), 0);
      if (v > bestV) { bestV = v; best = s.id; }
    }
    wins[best] = (wins[best] ?? 0) + 1;
  }
  const topShare = Math.max(...Object.values(wins)) / 300;
  const flag: S["StabilityFlag"] = topShare >= 0.8 ? "stable" : topShare >= 0.5 ? "moderate" : "unstable";
  const margin = ordered[0].total - ordered[1].total;
  const waterFavours = totals.slice().sort((a, b) => (score(b.s, "water", scenario) ?? 0) - (score(a.s, "water", scenario) ?? 0))[0].s;
  const soilFavours = totals.slice().sort((a, b) => (score(b.s, "soil", scenario) ?? 0) - (score(a.s, "soil", scenario) ?? 0))[0].s;
  const conflicts: S["Conflict"][] = waterFavours.id !== soilFavours.id
    ? [{ criteria: ["water", "soil"], text_es: `El criterio de agua favorece a «${waterFavours.name}» y el de suelo a «${soilFavours.name}»; el orden depende de la prioridad que se dé a cada objetivo.`, text_en: `The water criterion favours "${waterFavours.name}" while soil favours "${soilFavours.name}"; the order depends on how each objective is weighted.` }]
    : [];

  return {
    ...common,
    status: "ok",
    weights_effective: Object.fromEntries(CRITERIA.map((c) => [c, used.includes(c) ? weights[c] / usedW : 0])) as Weights,
    weight_coverage: ind("rank.weight_coverage", "Cobertura de pesos", "Weight coverage", Math.round(coverage * 100) / 100, "", "ranking"),
    ranking: ordered.map(({ s, total }, i) => ({
      strategy_version_id: s.id,
      name: s.name,
      rank: ind(`rank.pos.${s.id}`, "Posición", "Position", i + 1, "", "ranking") as S["IndicatorInteger"],
      total: ind(`rank.total.${s.id}`, "Puntuación total", "Total score", Number(total.toFixed(3)), "0–1", "ranking"),
      criteria: Object.fromEntries(CRITERIA.map((c) => {
        const v = score(s, c, scenario);
        return [c, {
          status: v === null ? "not_evaluable" : used.includes(c) ? "provisional" : "evaluable",
          indicator: v === null ? null : ind(`rank.raw.${s.id}.${c}`, c, c, v, "0–1", "criterion"),
          normalised: v === null ? null : ind(`rank.norm.${s.id}.${c}`, c, c, v, "0–1", "criterion"),
        }];
      })) as S["RankedStrategy"]["criteria"],
    })),
    partial_table: null,
    top_margin: ind("rank.top_margin", "Margen entre primero y segundo", "Top margin", Number(margin.toFixed(3)), "0–1", "ranking"),
    margin_within_uncertainty: margin < 0.05,
    decision_log,
    explanations: [{
      a_strategy_id: ordered[0].s.id,
      b_strategy_id: ordered[1].s.id,
      text_es: `«${ordered[0].s.name}» queda por encima de «${ordered[1].s.name}» con estos pesos; la diferencia es de ${margin.toFixed(2)} puntos.`,
      text_en: `"${ordered[0].s.name}" ranks above "${ordered[1].s.name}" with these weights; the gap is ${margin.toFixed(2)} points.`,
    }],
    stability: {
      flag,
      top1_share: Object.fromEntries(STRATEGIES.map((s) => [s.name, ind(`stab.top1.${s.id}`, "Fracción como primera", "Top-1 share", Number(((wins[s.id] ?? 0) / 300).toFixed(2)), "", "ranking")])),
      rank_corr_mean: ind("stab.corr", "Correlación media de órdenes", "Mean rank correlation", Number((0.4 + topShare * 0.5).toFixed(2)), "", "ranking"),
      conflicts,
      interpretation_es: "Mide sensibilidad a los pesos, no la probabilidad de ser la mejor.",
    },
  };
}

export type SoilState = { ph: "medido" | "desconocido"; phValue: number | null; declared: Record<string, { value: number; unit: string; basis: string }> };

export function soilStatuses(state: SoilState): S["SoilPropertyStatusDTO"][] {
  const unknown = (code: string): S["SoilPropertyStatusDTO"] => ({ property_code: code, status: "desconocido", value: null, method: null, depth_cm: null, sampled_at: null, representativeness: null, age_years: null, max_age_years: null });
  const props = ["ph", "om_pct", "texture", "awc_mm_per_m", "effective_root_depth_cm"];
  return props.map((code) => {
    if (code === "ph" && state.ph === "medido") {
      return {
        property_code: "ph",
        status: "medido" as const,
        value: ind("soil.ph", "pH", "pH", state.phValue, "pH", "soil_property"),
        method: "H2O_1:2.5",
        depth_cm: [ind("soil.depth.from", "Profundidad desde", "Depth from", 0, "cm", "soil_property") as S["IndicatorInteger"], ind("soil.depth.to", "Profundidad hasta", "Depth to", 20, "cm", "soil_property") as S["IndicatorInteger"]] as S["SoilPropertyStatusDTO"]["depth_cm"],
        sampled_at: "2025-03-12",
        representativeness: "parcela (fixture)",
        age_years: null,
        max_age_years: null,
      };
    }
    const declared = state.declared[code];
    if (declared) {
      return { ...unknown(code), status: "declarado" as const, value: ind(`soil.${code}`, code, code, declared.value, declared.unit, "soil_property"), method: `declarado: ${declared.basis}` };
    }
    return unknown(code);
  });
}

export function soilVoi(runId: string, state: SoilState): S["SoilVoiResponse"] {
  if (state.ph === "medido") {
    return { property_code: "ph", property_status: "medido", applicability: "already_measured", outcome: null, hypotheticals: null, lab_recommended: false, rationale_es: "El pH ya está medido; no se calcula estabilidad para esta propiedad.", range_citation: null };
  }
  if (runId === RUN_NO_MATRIX_ID) {
    return { property_code: "ph", property_status: "desconocido", applicability: "evaluable", outcome: "insufficient_info", hypotheticals: null, lab_recommended: false, rationale_es: "Falta la matriz de tolerancia de pH con cita (DP-10); no se puede evaluar.", range_citation: null };
  }
  const hyp = (v: number, top: string): S["Hypothetical"] => ({ value: ind(`voi.ph.${v}`, "pH hipotético", "Hypothetical pH", v, "pH", "soil_property"), label: "valor hipotético, no medido", top_strategy_id: top, excluded: [] });
  return {
    property_code: "ph",
    property_status: "desconocido",
    applicability: "evaluable",
    outcome: "ranking_sensitive",
    hypotheticals: [hyp(5, STRATEGY_ROT), hyp(6.5, STRATEGY_REF)],
    lab_recommended: true,
    rationale_es: "Con pH hipotético 5.0 cambia la primera posición respecto de pH hipotético 6.5 (valores hipotéticos del fixture).",
    range_citation: "Matriz del fixture (sin cita real)",
  };
}

export function runDto(runId: string): S["RunDTO"] {
  return {
    run_id: runId,
    status: "ok",
    mode: "exposure",
    label: "indicador_exposicion_climatica",
    mode_reasons: ["awc", "effective_depth", "initial_condition"],
    sandbox: true,
    synthetic_fixture: true,
    code_version: "synthetic-fixture",
    region_config_hash: sha("synthetic:region"),
    catalog_hash: sha("synthetic:catalog"),
    data_hash: sha("synthetic:data"),
    params_hash: sha("synthetic:params"),
    seed: 1,
  };
}

export function reportDto(id: string, runId: string, privacy: "internal" | "public", locale: "es" | "es+en"): S["ReportDTO"] {
  const parcelLine = privacy === "internal" ? " Parcela de prueba: parcel-synthetic-001." : "";
  const section = (title_es: string, title_en: string, body_es: string, body_en: string) => ({ title_es, title_en, body_es, body_en });
  const sections = [
    section("Resumen ejecutivo", "Executive summary", `Comparación de tres estrategias con un fixture sintético.${parcelLine} No es una recomendación automática.`, "Comparison of three strategies using a synthetic fixture. This is not an automatic recommendation."),
    section("Modo de cálculo", "Calculation mode", "Indicador de exposición climática (Modo A). Resultado provisional.", "Climate exposure indicator (Mode A). Provisional result."),
  ];
  const annex = [
    section("Supuestos y sensibilidad", "Assumptions and sensitivity", "Pef con usda_scs_fao; ea por punto de rocío; sensibilidad al método declarada.", "Pef with usda_scs_fao; ea from dew point; method sensitivity declared."),
    section("Referencias", "References", "Fixture sin referencias reales.", "Fixture without real references."),
  ];
  return {
    report_id: id,
    run_id: runId,
    locale,
    privacy_level: privacy,
    pdf_url: `/v1/reports/${id}/pdf`,
    sha256: sha(JSON.stringify({ sections, annex })),
    sections,
    annex,
  };
}
