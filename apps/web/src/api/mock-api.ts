import type { Plugin } from "vite";

import * as fx from "./mock-fixture";
import { toWire } from "./mock-wire";
import type { components } from "./draft.gen";

type S = components["schemas"];

export type MockApiResponse = {
  status: number;
  body: unknown;
};

export type MockContext = {
  query?: URLSearchParams;
  authenticated?: boolean;
  body?: string;
};

const noScientificFixture = "The local mock has no approved R1/R2 scientific fixture for this identifier; no result was calculated.";

type JobRecord = { polls: number; result: S["Job"]["result"]; onDone?: () => void; status: S["JobStatus"] };

type MockState = {
  soil: fx.SoilState;
  parcelDeleted: boolean;
  scenarios: Set<string>;
  jobs: Map<string, JobRecord>;
  reports: Map<string, S["ReportDTO"]>;
  counter: number;
};

function freshState(): MockState {
  return {
    soil: { ph: "desconocido", phValue: null, declared: {} },
    parcelDeleted: false,
    scenarios: new Set([fx.BASE, fx.COMBINED, fx.COMBINED_ALT]),
    jobs: new Map(),
    reports: new Map(),
    counter: 0,
  };
}

let state = freshState();

/** Test helper: restores the in-memory synthetic state. */
export function resetMockState() {
  state = freshState();
}

function problem(status: number, code: string, title: string, detail: string, hint?: string): MockApiResponse {
  const payload: S["Problem"] = { type: "about:blank", title, status, code, detail, ...(hint ? { hint } : {}) };
  return { status, body: payload };
}

const unauthenticated = () => problem(401, "UNAUTHENTICATED", "Authentication required", "This action needs a signed-in session.", "Inicie sesión para continuar.");
const isFixtureRun = (id: string) => id === fx.RUN_ID || id === fx.RUN_NO_MATRIX_ID;
const notComputed = (scenario: string) => problem(409, "SCENARIO_NOT_COMPUTED", "Scenario not computed", `Scenario ${scenario} has not been computed for this run.`, "Calcule el escenario desde el Laboratorio de rotaciones.");

function newJob(result: S["Job"]["result"], onDone?: () => void): S["Job"] {
  state.counter += 1;
  const job_id = `job-${state.counter}`;
  state.jobs.set(job_id, { polls: 0, result, onDone, status: "queued" });
  return { job_id, status: "queued", progress: 0 };
}

function parseJson<T>(text: string | undefined): T | null {
  if (!text) return null;
  try { return JSON.parse(text) as T; } catch { return null; }
}

function csvRowsFromMultipart(body: string): string[][] {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("parcel_code"));
  if (start < 0) return [];
  const rows: string[][] = [];
  for (let i = start; i < lines.length; i++) {
    if (lines[i].startsWith("--")) break;
    if (lines[i].trim()) rows.push(lines[i].split(","));
  }
  return rows;
}

function soilUpload(body: string): S["SoilUploadResult"] {
  const rows = csvRowsFromMultipart(body);
  if (rows.length < 2) return { accepted: [], errors: [{ row: 0, column: null, message: "No se encontró el encabezado esperado (parcel_code,…)." }] };
  const header = rows[0];
  const idx = (name: string) => header.indexOf(name);
  const errors: S["SoilRowError"][] = [];
  const accepted: Record<string, number> = {};
  rows.slice(1).forEach((cells, i) => {
    const row = i + 1;
    const get = (name: string) => (cells[idx(name)] ?? "").trim();
    const bad = cells.find((c) => /^[=+\-@]/.test(c.trim()) && Number.isNaN(Number(c)));
    if (bad !== undefined) { errors.push({ row, column: null, message: "La celda empieza con un carácter de fórmula y se rechaza." }); return; }
    const date = get("sample_date");
    if (date && new Date(date) > new Date()) errors.push({ row, column: "sample_date", message: "La fecha de muestra no puede ser futura." });
    const ph = get("ph");
    if (ph) {
      const n = Number(ph);
      if (!Number.isFinite(n) || n < 3 || n > 10) errors.push({ row, column: "ph", message: "El pH debe estar entre 3.0 y 10.0." });
      else if (!get("ph_method")) errors.push({ row, column: "ph_method", message: "Una propiedad con valor exige su método (ph_method)." });
      else {
        accepted.ph = (accepted.ph ?? 0) + 1;
        state.soil = { ...state.soil, ph: "medido", phValue: n };
      }
    }
    const parts = ["sand_pct", "silt_pct", "clay_pct"].map(get).filter(Boolean).map(Number);
    if (parts.length === 3 && Math.abs(parts.reduce((a, b) => a + b, 0) - 100) > 2) errors.push({ row, column: "sand_pct", message: "arena + limo + arcilla debe sumar 100 ± 2." });
  });
  return { accepted: Object.entries(accepted).map(([property_code, count]) => ({ property_code, rows: count })), errors };
}

function advanceJob(id: string): MockApiResponse {
  const job = state.jobs.get(id);
  if (!job) return problem(404, "NOT_FOUND", "Job not found", `No job ${id}.`);
  job.polls += 1;
  if (job.polls === 1) job.status = "running";
  else if (job.status !== "ok") { job.status = "ok"; job.onDone?.(); }
  const body: S["Job"] = { job_id: id, status: job.status, progress: job.status === "ok" ? 1 : 0.5, result: job.status === "ok" ? job.result : null, error: null };
  return { status: 200, body };
}

/** Deterministic mock used only by the Vite development server and the tests. */
export function mockResponseFor(method: string, pathname: string, context: MockContext = {}): MockApiResponse {
  const verb = method.toUpperCase();
  const query = context.query ?? new URLSearchParams();
  const authed = Boolean(context.authenticated);

  // Test-only: restores the in-memory synthetic state between acceptance tests.
  if (verb === "POST" && pathname === "/v1/__mock__/reset") {
    resetMockState();
    return { status: 200, body: { reset: true } };
  }

  if (verb === "GET" && pathname === "/v1/healthz") return { status: 200, body: { status: "ok", service: "milpa-r4-mock", mode: "mock" } };

  if (verb === "POST" && pathname === "/v1/auth/login") {
    const credentials = parseJson<{ email?: string; password?: string }>(context.body);
    if (!credentials?.email || !credentials.password) return problem(401, "UNAUTHENTICATED", "Invalid credentials", "Email and password are required.", "Revise sus datos de acceso.");
    const session: S["Session"] = { access_token: "mock-session-token", expires_in: 900, role: "tecnico" };
    return { status: 200, body: session };
  }
  if (verb === "GET" && pathname === "/v1/auth/me") {
    return authed ? { status: 200, body: { role: "tecnico", mock: true } } : problem(401, "UNAUTHENTICATED", "Local preview has no session", "Sign in first.");
  }

  if (verb === "GET" && pathname === "/v1/zones") return { status: 200, body: [{ zone_id: fx.ZONE_ID, region_id: fx.REGION_ID, name: fx.zoneDetail().name }] };

  const zoneQuality = pathname.match(/^\/v1\/zones\/([^/]+)\/data-quality$/);
  if (verb === "GET" && zoneQuality) {
    return zoneQuality[1] === fx.ZONE_ID ? { status: 200, body: fx.dataQuality() } : problem(404, "NOT_FOUND", "Zone not found", "Use the synthetic zone in mock mode.");
  }
  const zoneMatch = pathname.match(/^\/v1\/zones\/([^/]+)$/);
  if (verb === "GET" && zoneMatch) {
    return zoneMatch[1] === fx.ZONE_ID ? { status: 200, body: fx.zoneDetail() } : problem(404, "NOT_FOUND", "Zone not found", "Use the synthetic zone in mock mode.");
  }

  if (verb === "GET" && pathname === "/v1/catalog/strategies") return { status: 200, body: fx.strategyCatalog() };
  if (verb === "GET" && ["/v1/catalog/crops", "/v1/catalog/references"].includes(pathname)) return { status: 200, body: [] };

  const parcelSoil = pathname.match(/^\/v1\/parcels\/([^/]+)\/soil$/);
  if (verb === "GET" && parcelSoil) {
    if (parcelSoil[1] !== fx.PARCEL_ID) return { status: 200, body: [] };
    return state.parcelDeleted ? problem(404, "NOT_FOUND", "Parcel not found", "The parcel was deleted.") : { status: 200, body: fx.soilStatuses(state.soil) };
  }
  const parcelUpload = pathname.match(/^\/v1\/parcels\/([^/]+)\/soil-samples$/);
  if (verb === "POST" && parcelUpload) {
    if (!authed) return unauthenticated();
    return { status: 200, body: soilUpload(context.body ?? "") };
  }
  const declaration = pathname.match(/^\/v1\/parcels\/([^/]+)\/soil-declarations\/([^/]+)$/);
  if (verb === "PUT" && declaration) {
    if (!authed) return unauthenticated();
    const payload = parseJson<S["SoilDeclarationRequest"]>(context.body);
    if (!payload || !payload.basis || payload.basis.trim().length < 3) return problem(422, "VALIDATION_ERROR", "Invalid declaration", "A declared value needs its basis.", "Indique la base de la declaración.");
    state.soil.declared[declaration[2]] = { value: payload.value, unit: payload.unit, basis: payload.basis };
    const found = fx.soilStatuses(state.soil).find((p) => p.property_code === declaration[2]);
    return { status: 200, body: found };
  }
  const parcel = pathname.match(/^\/v1\/parcels\/([^/]+)$/);
  if (parcel) {
    if (verb === "GET") {
      if (parcel[1] !== fx.PARCEL_ID || state.parcelDeleted) return problem(404, "NOT_FOUND", "Parcel not found", "No such parcel.");
      const dto: S["ParcelDTO"] = { parcel_id: fx.PARCEL_ID, zone_id: fx.ZONE_ID, display_grid_m: 1000, display_lat: 14.825, display_lon: -89.395 };
      return { status: 200, body: dto };
    }
    if (verb === "DELETE") {
      if (!authed) return unauthenticated();
      return { status: 202, body: newJob(null, () => { state.parcelDeleted = true; }) };
    }
  }

  const runScenarios = pathname.match(/^\/v1\/runs\/([^/]+)\/scenarios$/);
  if (runScenarios) {
    if (verb === "GET") {
      return { status: 200, body: isFixtureRun(runScenarios[1]) ? [...state.scenarios].map((id) => fx.scenarioTag(id)) : [] };
    }
    if (verb === "POST") {
      if (!authed) return unauthenticated();
      if (!isFixtureRun(runScenarios[1])) return problem(501, "MOCK_ROUTE_PENDING", "Mock route pending", noScientificFixture);
      const request = parseJson<S["ScenarioRunRequest"]>(context.body) ?? {};
      const ids = request.grid ? ["T+2_P-20_D+0_Hrh", "T+4_P-20_D+0_Hrh"] : request.scenario_ids ?? [];
      return { status: 202, body: newJob({ run_id: runScenarios[1] }, () => ids.forEach((id) => state.scenarios.add(id))) };
    }
  }

  const runSub = pathname.match(/^\/v1\/runs\/([^/]+)\/([a-z-]+)$/);
  if (runSub) {
    const [, runId, sub] = runSub;
    const fixture = isFixtureRun(runId);
    const scenario = query.get("scenario") ?? "";
    const adaptation: S["AdaptationMode"] = query.get("adaptation") === "onset_rule" ? "onset_rule" : "none";

    if (verb === "GET" && sub === "summary") {
      if (!fixture) return { status: 200, body: { items: [], next_cursor: null } satisfies S["PageStrategyRiskDTO"] };
      return state.scenarios.has(scenario) ? { status: 200, body: fx.summary(scenario) } : notComputed(scenario);
    }
    if (verb === "GET" && sub === "climate-history") {
      return fixture ? { status: 200, body: fx.climateHistory() } : { status: 200, body: { state: "insufficient_data", message: noScientificFixture } };
    }
    if (verb === "GET" && sub === "heatmap") {
      if (!fixture) return problem(404, "NOT_FOUND", "Run not found", noScientificFixture);
      if (!state.scenarios.has(scenario)) return notComputed(scenario);
      const view = query.get("view") === "cycle" ? "cycle" : "strategy";
      const cycle = query.get("cycle");
      return { status: 200, body: fx.heatmap(view, query.get("strategy") ?? fx.STRATEGY_REF, cycle === null ? null : Number(cycle), scenario, adaptation) };
    }
    if (verb === "GET" && sub === "dekad-chart") {
      if (!fixture) return problem(404, "NOT_FOUND", "Run not found", noScientificFixture);
      if (!state.scenarios.has(scenario)) return notComputed(scenario);
      return { status: 200, body: fx.dekadChart(query.get("strategy") ?? fx.STRATEGY_REF, Number(query.get("cohort_year") ?? 2010), Number(query.get("cycle") ?? 0), (query.get("plant_date") ?? "2010-05-15").slice(-5), scenario, adaptation) };
    }
    if (verb === "POST" && sub === "rank") {
      if (!fixture) return problem(501, "MOCK_ROUTE_PENDING", "Mock route pending", noScientificFixture);
      const request = parseJson<S["RankRequest"]>(context.body);
      if (!request?.weights) return problem(422, "VALIDATION_ERROR", "Invalid ranking request", "weights are required.");
      const total = request.weights.water + request.weights.soil + request.weights.food + request.weights.income;
      if (Math.abs(total - 1) > 1e-6) return problem(422, "VALIDATION_ERROR", "Invalid weights", "The weights must add up to 1.", "La suma de pesos debe ser 1.");
      if (!state.scenarios.has(request.scenario_id)) return notComputed(request.scenario_id);
      return { status: 200, body: fx.rank(request.scenario_id, request.adaptation_mode ?? "none", request.weights, request.stability?.seed ?? 1) };
    }
    if (verb === "POST" && sub === "soil-voi") {
      return fixture ? { status: 200, body: fx.soilVoi(runId, state.soil) } : problem(501, "MOCK_ROUTE_PENDING", "Mock route pending", noScientificFixture);
    }
  }

  const run = pathname.match(/^\/v1\/runs\/([^/]+)$/);
  if (verb === "GET" && run) {
    return isFixtureRun(run[1]) ? { status: 200, body: fx.runDto(run[1]) } : { status: 200, body: { state: "mock_without_run_fixture", message: noScientificFixture } };
  }

  const job = pathname.match(/^\/v1\/jobs\/([^/]+)$/);
  if (verb === "GET" && job) return advanceJob(job[1]);

  if (verb === "POST" && pathname === "/v1/reports") {
    if (!authed) return unauthenticated();
    const request = parseJson<S["ReportRequestDraft"]>(context.body);
    if (!request?.run_id || !isFixtureRun(request.run_id)) return problem(501, "MOCK_ROUTE_PENDING", "Mock route pending", noScientificFixture);
    state.counter += 1;
    const reportId = `report-${state.counter}`;
    return { status: 202, body: newJob({ report_id: reportId }, () => state.reports.set(reportId, fx.reportDto(reportId, request.run_id, request.privacy_level, request.locale))) };
  }
  const reportPdf = pathname.match(/^\/v1\/reports\/([^/]+)\/pdf$/);
  if (verb === "GET" && reportPdf) return problem(501, "MOCK_ROUTE_PENDING", "No PDF in mock", "The mock does not render PDFs; the backend (R3) generates them.");
  const report = pathname.match(/^\/v1\/reports\/([^/]+)$/);
  if (verb === "GET" && report) {
    const dto = state.reports.get(report[1]);
    return dto ? { status: 200, body: dto } : problem(404, "NOT_FOUND", "Report not found", `No report ${report[1]}.`);
  }

  if (pathname.startsWith("/v1/")) return problem(501, "MOCK_ROUTE_PENDING", "Mock route pending", `The mock intentionally does not simulate ${verb} ${pathname} without an approved fixture.`);
  return problem(404, "MOCK_ROUTE_NOT_FOUND", "Route not found", `No local API route matches ${verb} ${pathname}.`);
}

export function mockApiPlugin(): Plugin {
  return {
    name: "milpa-r4-local-api-mock",
    enforce: "pre",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const url = new URL(request.url ?? "/", "http://vite.local");
        if (url.pathname !== "/v1" && !url.pathname.startsWith("/v1/")) return next();

        const chunks: Buffer[] = [];
        request.on("data", (chunk: Buffer) => chunks.push(chunk));
        request.on("end", () => {
          const result = toWire(request.method ?? "GET", url.pathname, mockResponseFor(request.method ?? "GET", url.pathname, {
            query: url.searchParams,
            authenticated: /^Bearer\s+\S+/.test(request.headers.authorization ?? ""),
            body: Buffer.concat(chunks).toString("utf8"),
          }));
          response.statusCode = result.status;
          response.setHeader("Content-Type", "application/json; charset=utf-8");
          response.setHeader("Cache-Control", "no-store");
          response.setHeader("X-Milpa-Api-Mode", "mock");
          response.end(JSON.stringify(result.body));
        });
      });
    },
  };
}
