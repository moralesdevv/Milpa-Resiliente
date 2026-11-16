import * as fx from "./mock-fixture";
import type { MockApiResponse } from "./mock-api";

/**
 * Capa "formato en el cable" del mock de desarrollo (ADR-018).
 *
 * `mock-api.ts` / `mock-fixture.ts` conservan el contrato del BORRADOR de R4 (cifras como `Indicator`,
 * listas desnudas, subida multipart…) porque sus pruebas lo verifican. La API real de R3 usa otros
 * DTO para zonas, calidad, suelo, parcelas, sesión, trabajos y listados. Esta capa traduce las
 * respuestas del mock a la forma real, de modo que la SPA corre igual contra el mock y contra R3.
 * Los valores siguen siendo los del fixture SINTÉTICO rotulado: aquí no se calcula nada.
 */
type Json = Record<string, unknown>;

const isObj = (v: unknown): v is Json => typeof v === "object" && v !== null && !Array.isArray(v);
const val = (v: unknown): number | null => (isObj(v) && typeof v.value === "number" ? v.value : typeof v === "number" ? v : null);
const MOCK_IP_ID = "00000000-0000-4000-8000-00000000f1c7"; // identificador ficticio, solo del mock
const SHA_ZERO = "0".repeat(64);

/** `ScenarioTag` del §15 lleva números simples (R4 los envolvía en Indicator en su borrador). */
export function deepScenarioPlain<T = unknown>(node: unknown): T {
  if (Array.isArray(node)) return node.map((n) => deepScenarioPlain(n)) as T;
  if (!isObj(node)) return node as T;
  const out: Json = {};
  for (const [k, v] of Object.entries(node)) {
    if (k === "scenario" && isObj(v) && isObj(v.delta_t_c)) {
      out[k] = { ...v, delta_t_c: val(v.delta_t_c), precip_factor: val(v.precip_factor), onset_delay_days: val(v.onset_delay_days) };
    } else out[k] = deepScenarioPlain(v);
  }
  return out as T;
}

export function scenarioToWire(tag: unknown): unknown {
  return (deepScenarioPlain({ scenario: tag }) as Json).scenario;
}

function problem(status: number, code: string, title: string, detail: string, errors: unknown[] = []): MockApiResponse {
  return { status, body: { type: "about:blank", title, status, code, detail, request_id: "mock", errors } };
}

function toJob(body: Json): Json {
  return {
    job_id: body.job_id,
    kind: "analysis_run",
    status: body.status,
    attempts: 0,
    location: `/v1/jobs/${String(body.job_id)}`,
    progress: body.progress ?? null,
    result: body.result ?? null,
    error: body.error ?? null,
    created_at: null,
    started_at: null,
    finished_at: null,
  };
}

function toSource(s: Json, i: number): Json {
  return { source_id: i + 1, code: s.code, product_name: s.product_name, institution: s.institution, is_nasa: s.is_nasa, version: s.version ?? null, url: s.url ?? null, citation: s.citation ?? null };
}

export function toWire(method: string, pathname: string, res: MockApiResponse): MockApiResponse {
  const verb = method.toUpperCase();
  const body = res.body;
  const versionRoute = pathname.match(/^\/v1\/catalog\/strategies\/([^/]+)\/versions\/(\d+)$/);
  if (verb === "GET" && versionRoute) return strategyVersion(versionRoute[1], Number(versionRoute[2]));
  if (res.status >= 400) return res;

  if (verb === "POST" && pathname === "/v1/auth/login" && isObj(body)) {
    const expiresIn = Number(body.expires_in ?? 900);
    return { status: 200, body: { access_token: body.access_token, token_type: "bearer", expires_at: new Date(Date.now() + expiresIn * 1000).toISOString(), expires_in: expiresIn, role: body.role } };
  }
  if (verb === "GET" && pathname === "/v1/zones" && Array.isArray(body)) return { status: 200, body: { items: body, next_cursor: null } };
  if (verb === "GET" && /^\/v1\/catalog\/(crops|references)$/.test(pathname) && Array.isArray(body)) return { status: 200, body: { items: body, next_cursor: null } };
  if (verb === "GET" && pathname === "/v1/catalog/strategies" && isObj(body) && Array.isArray(body.items)) {
    const items = body.items.filter(isObj).map((s) => ({ strategy_id: s.strategy_version_id, code: String(s.name ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-"), name: s.name, is_reference: Boolean(s.is_reference), changes_from_reference: s.changes_from_reference ?? [], latest_version: 1 }));
    return { status: 200, body: { items, next_cursor: body.next_cursor ?? null } };
  }
  const zone = pathname.match(/^\/v1\/zones\/([^/]+)$/);
  if (verb === "GET" && zone && isObj(body)) {
    const ctx = isObj(body.context) ? body.context : {};
    const cells = (Array.isArray(ctx.cells) ? ctx.cells : []).filter(isObj).map((c, i) => ({ cell_id: Number(c.cell_id) || i + 1, source: c.source, weight: val(c.weight) ?? 0, south: c.south, west: c.west, north: c.north, east: c.east }));
    return { status: 200, body: { zone_id: body.zone_id, region_id: body.region_id, name: body.name, elevation_m: val(body.elevation_m), slope_pct: val(body.slope_pct), ready_at: null, geometry: {}, soil_estimates: [], cells, sources: (Array.isArray(body.sources) ? body.sources : []).filter(isObj).map(toSource) } };
  }
  const quality = pathname.match(/^\/v1\/zones\/([^/]+)\/data-quality$/);
  if (verb === "GET" && quality && isObj(body)) {
    const coverage = (Array.isArray(body.coverage) ? body.coverage : []).filter(isObj).map((r) => ({ cell_id: null, variable: r.variable, year: r.year, n_expected: null, n_valid: null, pct_missing: val(r.missing_pct) }));
    const comparisons = (Array.isArray(body.comparisons) ? body.comparisons : []).filter(isObj).map((c) => ({ pair: c.pair, bias_mm_day: val(c.bias), correlation_daily: val(c.correlation), annual_ratio: {} }));
    return { status: 200, body: { zone_id: quality[1], dataset: { relative_path: "mock/fixture", sha256: SHA_ZERO, n_rows: coverage.length, contract_status: "mock" }, coverage, next_cursor: null, state: body.state ?? "ok", message: body.message ?? null, sources: (Array.isArray(body.sources) ? body.sources : []).filter(isObj).map(toSource), comparisons, ea_sensitivity_mm_day: val(body.ea_sensitivity), limitations: [] } };
  }
  if (verb === "GET" && /^\/v1\/parcels\/[^/]+\/soil$/.test(pathname) && Array.isArray(body)) {
    return { status: 200, body: body.filter(isObj).map((p) => ({ ...p, value: isObj(p.value) ? { value: val(p.value), unit: p.value.unit, ip_id: MOCK_IP_ID } : null, depth_cm: Array.isArray(p.depth_cm) ? p.depth_cm.map(val) : null, age_years: val(p.age_years), max_age_years: val(p.max_age_years) })) };
  }
  if (verb === "POST" && /^\/v1\/parcels\/[^/]+\/soil-samples$/.test(pathname) && isObj(body)) {
    const errors = (Array.isArray(body.errors) ? body.errors : []).filter(isObj);
    if (errors.length) return problem(422, "CSV_VALIDATION_FAILED", "El CSV de suelo no es válido", "Corrija las filas indicadas.", errors.map((e) => ({ loc: ["csv", e.row, e.column ?? null].filter((x) => x !== null), msg: e.message, code: "invalid_value" })));
    const accepted = Object.fromEntries((Array.isArray(body.accepted) ? body.accepted : []).filter(isObj).map((a) => [a.property_code, a.rows]));
    const rows = Math.max(0, ...Object.values(accepted).map(Number));
    return { status: 200, body: { contract: "SOIL_CSV_V1", rows_total: rows, rows_accepted: rows, accepted_by_property: accepted, persisted: true, dry_run: false } };
  }
  const parcel = pathname.match(/^\/v1\/parcels\/([^/]+)$/);
  if (verb === "GET" && parcel && isObj(body)) {
    return { status: 200, body: { parcel_id: body.parcel_id, zone_id: body.zone_id, farmer_id: null, code: null, area_ha: null, display_location: typeof body.display_lat === "number" ? { lat: body.display_lat, lon: body.display_lon } : null, display_grid_m: body.display_grid_m ?? null, created_at: new Date(0).toISOString() } };
  }
  if (isObj(body) && typeof body.job_id === "string") return { status: res.status, body: toJob(body) };
  if (verb === "GET" && /^\/v1\/runs\/[^/]+\/scenarios$/.test(pathname) && Array.isArray(body)) return { status: 200, body: body.map((t) => scenarioToWire(t)) };
  if (/^\/v1\/runs\//.test(pathname)) return { status: res.status, body: deepScenarioPlain(body) };
  return res;
}

/** Versión de estrategia (formato de R3) a partir de las estrategias del fixture sintético. */
function strategyVersion(id: string, version: number): MockApiResponse {
  const item = fx.strategyCatalog().items.find((s) => s.strategy_version_id === id);
  if (!item || version !== 1) return problem(404, "NOT_FOUND", "Versión no encontrada", "Estrategia o versión inexistente en el fixture.");
  const cycles = item.cycles.map((c, i) => {
    const [start, end] = String(c.planting_window ?? "").split("–");
    return {
      cycle_idx: i + 1,
      agri_year_offset: 0,
      season: c.season,
      window_mode: "fixed_season_window",
      plant_window_start: start || null,
      plant_window_end: end || null,
      rel_lag_days: null,
      fallow_after_days: 0,
      soil_carryover: false,
      components: c.crops.map((crop) => ({ variety_id: MOCK_IP_ID, role: "principal", area_fraction: 1 / c.crops.length, plant_offset_days: 0, crop_code: crop, crop_name_es: crop, crop_name_en: crop })),
    };
  });
  return { status: 200, body: { strategy_version_id: id, strategy_id: id, version, horizon_years: Math.max(1, cycles.length), anchor_cycle_idx: 1, cycles } };
}
