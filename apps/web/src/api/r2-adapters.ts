import type { components } from "./types.gen";

/**
 * Capa de adaptación R3 → vistas de R4 para los resultados REALES del motor (milpa_core, R2).
 *
 * El motor publica números simples + procedencia por indicador; las pantallas de R4 dibujan cada cifra
 * como `Indicator`. Aquí solo se cambian nombres/estructura: no se calcula ni se inventa ningún valor.
 * La procedencia de cada celda se hereda del indicador de R2 de la misma estrategia/corrida.
 */
type S = components["schemas"];
type Prov = S["ProvenanceInfo"];
type Num = S["IndicatorNumber"];
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Raw = any;

const FALLBACK_PROVENANCE: Prov = {
  provenance: "desconocido",
  evidence: null as never,
  evidence_rule: "sin_procedencia_en_la_api",
  sources: [],
  method: "El motor no entregó procedencia para esta cifra.",
  assumptions: [],
  limitations: [],
} as Prov;

export function ind(code: string, label: string, value: number | null | undefined, unit: string, provenance: Prov | undefined, opts: { kind?: S["IndicatorKind"]; provisional?: boolean; reason?: string } = {}): Num {
  return {
    code,
    label_es: label,
    label_en: label,
    value: value ?? null,
    unit,
    kind: opts.kind ?? "exposure",
    provisional: opts.provisional ?? true,
    reason: opts.reason ?? null,
    provenance: provenance ?? FALLBACK_PROVENANCE,
  } as Num;
}

function scenarioTag(tag: Raw, prov?: Prov): S["ScenarioTag"] {
  return {
    ...tag,
    delta_t_c: ind("delta_t_c", "ΔT", tag.delta_t_c, "°C", prov, { kind: "scenario_param" as never, provisional: false }),
    precip_factor: ind("precip_factor", "Factor de precipitación", tag.precip_factor, "1", prov, { kind: "scenario_param" as never, provisional: false }),
    onset_delay_days: ind("onset_delay_days", "Retraso del inicio de lluvias", tag.onset_delay_days, "d", prov, { kind: "scenario_param" as never, provisional: false }),
  } as S["ScenarioTag"];
}

/** summary: `{strategies: [...]}` de R2 → página de `StrategyRiskDTO` (id = código de estrategia). */
export function toSummaryPage(raw: Raw): S["PageStrategyRiskDTO"] {
  const items = (raw.strategies ?? []).map((s: Raw) => ({
    ...s,
    strategy_version_id: s.strategy,
    by_cycle: (s.by_cycle ?? []).map((c: Raw) => ({ ...c, strategy_version_id: s.strategy, variety_id: c.variety })),
  }));
  return { items, next_cursor: null } as unknown as S["PageStrategyRiskDTO"];
}

/** heatmap: todas las estrategias de R2 → `HeatmapDTO` de la estrategia/vista pedida. */
export function toHeatmap(raw: Raw, view: "cycle" | "strategy", strategy: string): S["HeatmapDTO"] | null {
  const block = raw.heatmaps?.[strategy];
  const h = block?.[view] ?? block?.strategy ?? block?.cycle;
  if (!h) return null;
  const prov: Prov | undefined = raw.provenance_by_strategy?.[strategy];
  const windows: string[][] = h.consistent_windows ?? [];
  const win = windows.find((w) => w.length > 0);
  return {
    view: h.view,
    strategy_version_id: strategy,
    cycle_idx: h.cycle_idx ?? null,
    variety_id: h.variety ?? null,
    scenario: scenarioTag(raw.scenario, prov),
    mode: raw.mode,
    label: raw.label,
    plant_md: h.plant_md,
    years: h.years,
    state: h.state,
    severity: (h.severity_mm as (number | null)[][]).map((row) => row.map((v) => (v == null ? null : ind("severity_mm", "Severidad de exposición", v, "mm", prov)))),
    pct_critical_by_date: (h.pct_critical_by_date as (number | null)[]).map((v) => (v == null ? null : ind("pct_critical", "Ciclos críticos", v, "%", prov))),
    n_decided_by_date: (h.n_decided_by_date as number[]).map((v) => ind("n_decided", "Ciclos decididos", v, "ciclos", prov, { kind: "coverage" as never })),
    aggregation_rule: h.aggregation_rule ?? null,
    thresholds_used: [],
    consistent_window: win ? { start_md: win[0], end_md: win[win.length - 1] } : null,
    provenance: prov ?? FALLBACK_PROVENANCE,
  } as unknown as S["HeatmapDTO"];
}

/** dekad-chart: una cohorte de R2 → `DekadChartDTO`; el acumulado es la suma corrida de las decenas. */
export function toDekadChart(raw: Raw, provenance?: Prov): S["DekadChartDTO"] {
  const prov = provenance;
  const addDays = (iso: string, n: number) => {
    const d = new Date(`${iso}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  let pefCum = 0;
  let etcCum = 0;
  const dekads = (raw.dekads ?? []).map((d: Raw) => ({
    idx: d.idx,
    start: d.start,
    end: addDays(d.start, d.n_days - 1),
    pef_mm: ind("pef_mm", "Precipitación efectiva", d.pef_mm, "mm", prov),
    etc_mm: ind("etc_mm", "Demanda del cultivo (ETc)", d.etc_mm, "mm", prov),
    exposure_mm: ind("exposure_mm", "Exposición", d.exposure_mm, "mm", prov),
    critical_stage: d.critical_stage ?? null,
    over_threshold: d.over_threshold ?? null,
  }));
  const cumulative = (raw.dekads ?? []).map((d: Raw) => {
    pefCum += d.pef_mm ?? 0;
    etcCum += d.etc_mm ?? 0;
    return {
      idx: d.idx,
      pef_cum_mm: ind("pef_cum_mm", "Precipitación efectiva acumulada", pefCum, "mm", prov),
      etc_cum_mm: ind("etc_cum_mm", "Demanda acumulada (ETc)", etcCum, "mm", prov),
    };
  });
  return {
    strategy_version_id: raw.strategy,
    cohort_year: raw.cohort_year,
    cycle_idx: raw.cycle_idx,
    plant_date: raw.plant_date,
    scenario: scenarioTag(raw.scenario, prov),
    dekads,
    stage_bands: raw.stage_bands ?? [],
    etc_system_exploratory: raw.etc_system_exploratory
      ? (raw.etc_system_exploratory as (number | null)[]).map((v) => (v == null ? null : ind("etc_system", "ETc del sistema (exploratoria)", v, "mm", prov)))
      : null,
    cumulative,
    provenance: { peff_method: raw.peff_method, reasons: raw.reasons, state: raw.state, provisional: raw.provisional },
  } as unknown as S["DekadChartDTO"];
}

/** rank: respuesta de R2 → `RankResponse`; los nombres de estrategia salen del resumen ya cargado. */
export function toRankResponse(raw: Raw, names: Record<string, string>): S["RankResponse"] {
  const prov = {
    provenance: "modelado",
    evidence: raw.evidence ?? null,
    evidence_rule: "milpa_core.rank",
    sources: [],
    method: "Ranking multicriterio de milpa_core sobre los criterios evaluables",
    assumptions: [],
    limitations: raw.provisional ? ["resultado provisional (umbrales o catálogos sandbox)"] : [],
  } as unknown as Prov;
  const nameOf = (id: string) => names[id] ?? id;
  const ranking = (raw.ranking ?? []).map((r: Raw) => ({
    strategy_version_id: r.strategy,
    name: nameOf(r.strategy),
    rank: ind("rank", "Posición", r.rank, "posición", prov, { kind: "ranking" as never }),
    total: ind("rank_total", "Puntaje total", r.total, "0–1", prov, { kind: "ranking" as never, provisional: Boolean(raw.provisional) }),
    criteria: Object.fromEntries(Object.entries(r.criteria ?? {}).map(([k, c]) => {
      const cell = c as Raw;
      return [k, {
        status: cell.status,
        indicator: cell.value == null ? null : ind(`criterion_${k}`, k, cell.value, cell.unit ?? "0–1", prov, { kind: "ranking" as never, provisional: cell.status === "provisional", reason: cell.reason }),
        normalised: cell.normalised == null ? null : ind(`criterion_${k}_norm`, k, cell.normalised, "0–1", prov, { kind: "ranking" as never }),
      }];
    })),
  }));
  const stab = raw.stability ?? {};
  return {
    ranking_id: raw.ranking_id ?? "00000000-0000-0000-0000-000000000000",
    status: raw.status,
    criteria_used: raw.criteria_used,
    weights: raw.weights,
    weights_effective: raw.weights_effective ?? null,
    weight_coverage: raw.weight_coverage == null ? null : ind("weight_coverage", "Cobertura de pesos", raw.weight_coverage, "0–1", prov, { kind: "ranking" as never }),
    ranking,
    partial_table: raw.partial_table ?? null,
    top_margin: raw.top_margin == null ? null : ind("top_margin", "Margen del primer lugar", raw.top_margin, "0–1", prov, { kind: "ranking" as never }),
    margin_within_uncertainty: raw.margin_within_uncertainty ?? null,
    evidence: raw.evidence ?? undefined,
    provisional: Boolean(raw.provisional),
    decision_log: (raw.decision_log ?? []).map((d: Raw) => ({
      kind: d.decision === "criterio_fuera_del_soporte_comun" ? "criterion_excluded" : d.decision === "pesos_renormalizados" ? "weights_renormalised" : "other",
      criterion: d.criterion ?? null,
      message_es: [d.decision, d.note].filter(Boolean).join(": "),
    })),
    stability: {
      flag: stab.flag,
      top1_share: Object.fromEntries(Object.entries(stab.top1_share ?? {}).map(([k, v]) => [k, ind("top1_share", `Primer lugar: ${nameOf(k)}`, v as number, "fracción", prov, { kind: "ranking" as never })])),
      rank_corr_mean: ind("rank_corr_mean", "Correlación media de posiciones", stab.rank_corr_mean, "−1–1", prov, { kind: "ranking" as never }),
      conflicts: stab.conflicts ?? [],
      interpretation_es: stab.interpretation_es ?? "",
    },
    explanations: (raw.explanations ?? []).map((e: Raw) => ({ a_strategy_id: e.a, b_strategy_id: e.b, text_es: e.text_es })),
  } as unknown as S["RankResponse"];
}
