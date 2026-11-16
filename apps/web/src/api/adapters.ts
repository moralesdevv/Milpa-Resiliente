import type { components } from "./types.gen";

/**
 * Capa de adaptación R3 → vistas de R4 (ADR-018).
 *
 * R4 dibujó sus pantallas sobre un borrador donde TODA cifra viaja como `Indicator` (SPEC-01). La API
 * de R3 entrega, para zonas, calidad de datos, suelo y parcelas, valores simples (más el enlace
 * `ip_id` cuando la cifra tiene procedencia en la base). Estos adaptadores convierten sin inventar:
 * un valor sin procedencia estructurada se rotula con procedencia `desconocido` y evidencia nula
 * (así lo exige la regla del README: `desconocido` ⇔ sin nivel de evidencia).
 */
type S = components["schemas"];
export type NumberIndicator = S["IndicatorNumber"];

const NO_PROVENANCE_REASON =
  "The API provides this value without structured provenance (Indicator contract pending: SPEC-01).";

/** Envuelve un número simple de la API como `Indicator` con procedencia desconocida (no inventada). */
export function plain(
  code: string,
  label: string,
  value: number | null,
  unit: string,
  kind: S["IndicatorKind"] = "climate_input",
  provenance: S["Provenance"] = "desconocido",
): NumberIndicator {
  return {
    code,
    label_es: label,
    label_en: label,
    value,
    unit,
    kind,
    provisional: true,
    reason: NO_PROVENANCE_REASON,
    provenance: {
      provenance,
      evidence: null,
      evidence_rule: "sin_procedencia_en_la_api",
      sources: [],
      method: NO_PROVENANCE_REASON,
      assumptions: [],
      limitations: [],
    },
  } as NumberIndicator;
}

type ZoneDetail = S["ZoneDetail"];
type DataQuality = S["DataQualityOut"];
type SoilStatus = S["SoilPropertyStatusOut"];
type SoilStatusCode = S["PropertyStatus"];

export type ZoneView = {
  zone_id: string;
  region_id: string;
  name: string;
  elevation: NumberIndicator | null;
  slope: NumberIndicator | null;
  sources: S["SourceOut"][];
  context: ZoneContextView;
};

export type ZoneContextView = {
  state: "ok" | "insufficient_data";
  message?: string;
  synthetic_fixture?: boolean;
  cells: { cell_id: string; source: string; weight: NumberIndicator; south: number; west: number; north: number; east: number }[];
  /** Outline of the analysis zone (GeoJSON geometry from the API), drawn as a context layer. */
  area: unknown;
  crops: { code: string; name_es: string; name_en: string; seasons: string[]; calendar_validated: boolean }[];
  pending: string[];
};

export function toZoneView(zone: ZoneDetail): ZoneView {
  const cells = (zone.cells ?? []).map((cell) => ({
    cell_id: String(cell.cell_id),
    source: cell.source,
    weight: plain("zone_cell_weight", "Weight of the cell in the zone", cell.weight, "1"),
    south: cell.south,
    west: cell.west,
    north: cell.north,
    east: cell.east,
  }));
  return {
    zone_id: zone.zone_id,
    region_id: zone.region_id,
    name: zone.name,
    // Both figures are zonal means over the zone polygon computed by R1's DEM loader (Copernicus GLO-30).
    elevation: zone.elevation_m == null ? null : {
      ...plain("elevation_m", "Mean elevation inside the zone (Copernicus GLO-30 DEM)", zone.elevation_m, "m"),
      label_es: "Elevación media dentro de la zona (DEM Copernicus GLO-30)",
    },
    slope: zone.slope_pct == null ? null : {
      ...plain("slope_pct", "Mean slope inside the zone (Copernicus GLO-30 DEM)", zone.slope_pct, "%"),
      label_es: "Pendiente media dentro de la zona (DEM Copernicus GLO-30)",
    },
    sources: zone.sources ?? [],
    context: {
      state: cells.length ? "ok" : "insufficient_data",
      message: cells.length ? undefined : "The zone has no registered climate cells.",
      cells,
      area: zone.geometry ?? null,
      // Cultivos, temporadas y calendarios dependen del catálogo y del region pack de R1 (pending).
      // Crops, seasons and pending decisions come from the region pack the engine actually uses (sandbox).
      crops: (zone.agri_context?.crops ?? []).map((crop) => ({
        code: String(crop.code),
        name_es: String(crop.name_es),
        name_en: String(crop.name_en),
        seasons: ((crop.seasons as string[] | undefined) ?? []).map((code) => {
          const season = (zone.agri_context?.seasons ?? []).find((item) => item.code === code);
          const window = season?.plant_window as string[] | undefined;
          return window ? `${code} (${window[0]} to ${window[1]})` : code;
        }),
        calendar_validated: Boolean(crop.calendar_validated),
      })),
      pending: zone.agri_context?.pending ?? ["Crops, seasons and agricultural calendar: pending validation (no region pack available)."],
    },
  };
}

export type QualityView = {
  state: "ok" | "insufficient_data";
  message?: string;
  coverage: { variable: string; year: number; missing_pct: NumberIndicator }[];
  comparisons: { pair: string; bias: NumberIndicator; correlation: NumberIndicator }[];
  ea_sensitivity: NumberIndicator | null;
  sources: S["SourceOut"][];
  limitations: string[];
};

export function toQualityView(q: DataQuality): QualityView {
  return {
    state: q.state ?? "ok",
    message: q.message ?? undefined,
    coverage: q.coverage.map((row) => ({
      variable: row.variable,
      year: row.year,
      missing_pct: plain(`missing_pct_${row.variable}`, `Missing ${row.variable}`, row.pct_missing ?? null, "%"),
    })),
    comparisons: (q.comparisons ?? []).map((c) => ({
      pair: c.pair,
      bias: plain("precip_bias", "Bias (IMERG − POWER)", c.bias_mm_day ?? null, "mm/day", "climate_input"),
      correlation: plain("precip_corr_daily", "Daily correlation", c.correlation_daily ?? null, "1", "climate_input"),
    })),
    ea_sensitivity:
      q.ea_sensitivity_mm_day == null
        ? null
        : plain("ea_sensitivity", "ET0 difference between vapour-pressure routes", q.ea_sensitivity_mm_day, "mm/day", "climate_input"),
    sources: q.sources ?? [],
    limitations: q.limitations ?? [],
  };
}

const PROVENANCE_OF_STATUS: Partial<Record<SoilStatusCode, S["Provenance"]>> = {
  medido: "medido",
  declarado: "declarado",
  estimado: "estimado",
};

export type SoilStatusView = Omit<SoilStatus, "value" | "age_years" | "max_age_years" | "depth_cm"> & {
  value: NumberIndicator | null;
  depth_cm: [NumberIndicator, NumberIndicator] | null;
  age_years: NumberIndicator | null;
  max_age_years: NumberIndicator | null;
};

export function toSoilStatusView(p: SoilStatus): SoilStatusView {
  const prov = PROVENANCE_OF_STATUS[p.status] ?? "desconocido";
  return {
    ...p,
    value: p.value ? plain(`soil_${p.property_code}`, p.property_code, p.value.value, p.value.unit, "soil_property", prov) : null,
    depth_cm: p.depth_cm ? [plain("depth_from_cm", "Depth from", p.depth_cm[0], "cm", "soil_property"), plain("depth_to_cm", "Depth to", p.depth_cm[1], "cm", "soil_property")] : null,
    age_years: p.age_years == null ? null : plain("sample_age", "Sample age", p.age_years, "years", "soil_property"),
    max_age_years: p.max_age_years == null ? null : plain("max_age", "Maximum validity", p.max_age_years, "years", "soil_property"),
  };
}

/** Resultado de la carga de CSV tal como la UI lo muestra (200 con conteos, o 422 con errores por fila). */
export type UploadView = {
  accepted: { property_code: string; rows: number }[];
  errors: { row: number; column?: string; message: string }[];
};

export function uploadFromOk(r: S["SoilCsvResult"]): UploadView {
  return { accepted: Object.entries(r.accepted_by_property).map(([property_code, rows]) => ({ property_code, rows })), errors: [] };
}

export function uploadFromProblem(p: S["ProblemDetail"]): UploadView {
  const errors = (p.errors ?? []).map((e) => {
    const loc = e.loc ?? [];
    const row = typeof loc[1] === "number" ? loc[1] : 0;
    const column = typeof loc[2] === "string" ? loc[2] : undefined;
    return { row, column, message: e.msg };
  });
  return { accepted: [], errors };
}
