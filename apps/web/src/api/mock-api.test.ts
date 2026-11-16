import { beforeEach, describe, expect, it } from "vitest";

import { mockResponseFor, resetMockState } from "./mock-api";
import { PARCEL_ID, RUN_ID } from "./mock-fixture";

const authed = { authenticated: true };

describe("R4 local API mock (synthetic fixture only)", () => {
  beforeEach(() => resetMockState());

  it("serves one visibly labeled synthetic zone", () => {
    const response = mockResponseFor("GET", "/v1/zones");
    const zones = response.body as Array<Record<string, unknown>>;
    expect(response.status).toBe(200);
    expect(zones).toHaveLength(1);
    expect(String(zones[0].name)).toContain("SINTÉTICA");
  });

  it("returns empty computed collections for runs that have no fixture", () => {
    expect(mockResponseFor("GET", "/v1/runs/run-1/scenarios")).toEqual({ status: 200, body: [] });
    expect(mockResponseFor("GET", "/v1/runs/run-1/summary")).toEqual({ status: 200, body: { items: [], next_cursor: null } });
  });

  it("does not fake scientific calculations for unknown runs", () => {
    expect(mockResponseFor("POST", "/v1/runs/run-1/rank").status).toBe(501);
  });

  it("requires a session for mutations", () => {
    expect(mockResponseFor("POST", "/v1/reports", { body: "{}" }).status).toBe(401);
    expect(mockResponseFor("DELETE", `/v1/parcels/${PARCEL_ID}`).status).toBe(401);
    expect(mockResponseFor("POST", `/v1/runs/${RUN_ID}/scenarios`, { body: "{}" }).status).toBe(401);
  });

  it("answers 409 SCENARIO_NOT_COMPUTED for combinations outside the computed grid", () => {
    const response = mockResponseFor("GET", `/v1/runs/${RUN_ID}/summary`, { query: new URLSearchParams("scenario=T+4_P-20_D+0_Hrh&adaptation=none") });
    expect(response.status).toBe(409);
    expect(response.body).toMatchObject({ code: "SCENARIO_NOT_COMPUTED" });
  });

  it("keeps unknown soil properties unknown after a CSV that only has pH (T-P10)", () => {
    const csv = "--b\r\nContent-Disposition: form-data; name=\"file\"; filename=\"s.csv\"\r\n\r\nparcel_code,sample_date,ph,ph_method,om_pct\r\nP-014,2025-03-12,5.8,H2O_1:2.5,\r\n--b--";
    const upload = mockResponseFor("POST", `/v1/parcels/${PARCEL_ID}/soil-samples`, { ...authed, body: csv });
    expect(upload.body).toMatchObject({ accepted: [{ property_code: "ph", rows: 1 }], errors: [] });
    const soil = mockResponseFor("GET", `/v1/parcels/${PARCEL_ID}/soil`).body as Array<{ property_code: string; status: string }>;
    expect(soil.find((p) => p.property_code === "ph")?.status).toBe("medido");
    expect(soil.find((p) => p.property_code === "om_pct")?.status).toBe("desconocido");
  });

  it("rejects a pH without its method and formula cells", () => {
    const csv = "parcel_code,sample_date,ph,ph_method\r\nP-014,2025-03-12,5.8,\r\nP-014,2025-03-12,=1+1,H2O\r\n";
    const upload = mockResponseFor("POST", `/v1/parcels/${PARCEL_ID}/soil-samples`, { ...authed, body: csv });
    const errors = (upload.body as { errors: Array<{ column: string | null }> }).errors;
    expect(errors.some((e) => e.column === "ph_method")).toBe(true);
    expect(errors.length).toBeGreaterThanOrEqual(2);
  });

  it("changes the order when weights move and reports a stability flag from the four-value enum", () => {
    const request = (water: number) => JSON.stringify({ scenario_id: "BASE", adaptation_mode: "none", weights: { water, soil: (1 - water) / 3, food: (1 - water) / 3, income: (1 - water) / 3 }, missing_policy: "common_support", stability: { seed: 1 } });
    const heavyWater = mockResponseFor("POST", `/v1/runs/${RUN_ID}/rank`, { body: request(0.85) }).body as { ranking: Array<{ strategy_version_id: string }>; stability: { flag: string } };
    const lightWater = mockResponseFor("POST", `/v1/runs/${RUN_ID}/rank`, { body: request(0.05) }).body as { ranking: Array<{ strategy_version_id: string }>; stability: { flag: string } };
    expect(heavyWater.ranking[0].strategy_version_id).not.toBe(lightWater.ranking[0].strategy_version_id);
    expect(["stable", "moderate", "unstable", "insufficient"]).toContain(heavyWater.stability.flag);
  });

  it("excludes a criterion for every strategy when one strategy lacks it (common support)", () => {
    const body = JSON.stringify({ scenario_id: "BASE", adaptation_mode: "none", weights: { water: 0.25, soil: 0.25, food: 0.25, income: 0.25 }, missing_policy: "common_support", stability: {} });
    const rank = mockResponseFor("POST", `/v1/runs/${RUN_ID}/rank`, { body }).body as { criteria_used: string[]; weight_coverage: { value: number } };
    expect(rank.criteria_used).not.toContain("food");
    expect(rank.weight_coverage.value).toBe(0.75);
  });

  it("returns insufficient with a partial table when coverage is below the minimum", () => {
    const body = JSON.stringify({ scenario_id: "BASE", adaptation_mode: "none", weights: { water: 0.1, soil: 0, food: 0.9, income: 0 }, missing_policy: "common_support", stability: {} });
    const rank = mockResponseFor("POST", `/v1/runs/${RUN_ID}/rank`, { body }).body as { status: string; ranking: unknown[]; partial_table: unknown[] };
    expect(rank.status).toBe("insufficient");
    expect(rank.ranking).toHaveLength(0);
    expect(rank.partial_table.length).toBeGreaterThan(0);
  });

  it("runs report generation as a job that finishes on the second poll", () => {
    const job = mockResponseFor("POST", "/v1/reports", { ...authed, body: JSON.stringify({ run_id: RUN_ID, locale: "es+en", privacy_level: "public" }) });
    expect(job.status).toBe(202);
    const id = (job.body as { job_id: string }).job_id;
    expect((mockResponseFor("GET", `/v1/jobs/${id}`).body as { status: string }).status).toBe("running");
    const done = mockResponseFor("GET", `/v1/jobs/${id}`).body as { status: string; result: { report_id: string } };
    expect(done.status).toBe("ok");
    const report = mockResponseFor("GET", `/v1/reports/${done.result.report_id}`).body as { privacy_level: string; sections: Array<{ body_es: string }> };
    expect(report.privacy_level).toBe("public");
    expect(JSON.stringify(report)).not.toContain("parcel-synthetic-001");
  });

  it("does not render PDFs in the mock", () => {
    expect(mockResponseFor("GET", "/v1/reports/x/pdf").status).toBe(501);
  });
});
