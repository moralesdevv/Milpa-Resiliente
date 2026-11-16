/**
 * English display text for the fixed messages the scientific engine (R2) emits in Spanish.
 * Only exact known messages and one sentence template are translated; anything unknown is shown as
 * received (never guessed). This changes presentation only, not values or meaning.
 */
const EXACT: Record<string, string> = {
  "ET0 es modelada, no medida": "ET0 is modelled, not measured",
  "ajuste climático de Kc desactivado (sin RHmin)": "Climate adjustment of Kc disabled (no minimum relative humidity available)",
  "escenario sintético": "synthetic scenario",
  "indicador de exposición climática: no es déficit real de agua del suelo": "Climate exposure indicator: not an actual soil water deficit",
  "modo sandbox: catálogos y umbrales provisionales — no usar para decisión": "Sandbox mode: catalogs and thresholds are provisional — do not use for decisions",
  "umbral provisional — no usar para decisión": "Provisional threshold — do not use for decisions",
  "umbral provisional": "Provisional threshold",
  "provisional_sin_cita": "Provisional: the threshold has no citation",
  "datos_insuficientes": "Insufficient data",
  "ea_sensible_a_la_ruta": "Result sensitive to the vapour-pressure route",
  "peff_sensible_al_metodo": "Result sensitive to the effective-rainfall method",
  "fenologia_fija_en_dias": "Crop phenology is fixed in days (no temperature response)",
  "sin_continuidad_de_suelo": "No soil continuity between cycles",
  "sensible_a_condicion_inicial": "Sensitive to the initial soil condition",
  "escenario_sensible_a_humedad": "Scenario sensitive to the humidity assumption",
  "aproximación exploratoria": "Exploratory approximation",
  "La estabilidad mide la sensibilidad del orden a variaciones de los pesos de prioridad, no la probabilidad de que una estrategia sea la mejor.": "Stability measures how sensitive the order is to changes in the priority weights; it is not the probability that a strategy is the best.",
  "sale del total para todas: ninguna gana por tener menos datos": "Left out of the total for every strategy: none wins by having less data",
  "sin diferencia": "no difference",
  "sin precios con fuente; comparación cualitativa": "No sourced prices; qualitative comparison only",
  "sin rendimiento de referencia o composición con cita": "No cited reference yield or food composition",
  "índice 0–1": "index 0–1",
  "criterio_fuera_del_soporte_comun": "Criterion left out (not available for every strategy)",
  "fecha_ancla_para_ranking": "Anchor planting date used for the ranking",
  "convención de día de POWER e IMERG frente a UTC-6 [Verificar]": "Day convention of POWER and IMERG versus UTC-6 [to be verified]",
  "evidencia de lluvia: B solo con validación en la zona (estación); sin ella, C": "Rainfall evidence: B only with validation in the zone (weather station); without it, C",
  "NASA POWER diario (comunidad AG)": "NASA POWER daily (AG community)",
  "NASA (reanálisis MERRA-2 y CERES)": "NASA (MERRA-2 and CERES reanalysis)",
  "GPM IMERG Final Run diario, 0.1°": "GPM IMERG Final Run daily, 0.1°",
  "año": "year",
  "años": "years",
  "días": "days",
};

const CRITERIA: Record<string, string> = {
  "seguridad hídrica": "water security",
  "salud del suelo": "soil health",
  "alimentación familiar": "household food supply",
  "ingresos": "income",
};

export function en(text: string): string {
  const exact = EXACT[text];
  if (exact) return exact;
  if (text.includes(" supera a ")) {
    return text.split("; ").map((part) => {
      const m = /^(\S+) supera a (\S+) en (.+?) \(([+-][\d.]+)\)$/.exec(part);
      return m ? `${m[1]} outperforms ${m[2]} on ${CRITERIA[m[3]] ?? m[3]} (${m[4]})` : part;
    }).join("; ");
  }
  const outliers = /^POWER tiene (\d+) días atípicos \(>= (\d+) mm con IMERG < (\d+) mm\); su lluvia como respaldo es poco confiable$/.exec(text);
  if (outliers) return `POWER has ${outliers[1]} outlier days (>= ${outliers[2]} mm while IMERG < ${outliers[3]} mm); its rainfall is an unreliable fallback`;
  const used = /^subindicadores usados: (.+)$/.exec(text);
  if (used) return `Sub-indicators used: ${used[1]}`;
  return text;
}

/** Deep copy with every known Spanish engine message replaced by its English display text. */
export function localize<T>(value: T): T {
  if (typeof value === "string") return en(value) as T;
  if (Array.isArray(value)) return value.map((item) => localize(item)) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, localize(v)])) as T;
  }
  return value;
}
