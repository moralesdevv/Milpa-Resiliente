import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, assertResponse } from "../api/client";
import { usePublicAccess } from "../api/public-access";
import { useSession } from "../api/session";
import { BrandMark } from "../components/common/Icon";

/**
 * LAUNCH DEMO: runs the real workflow against the real API and then opens the calendar screen.
 *   sign in → pilot zone → base run (job) → a small set of synthetic scenarios (job) → "How the calendar changed".
 * A run that already exists for the zone is reused. Nothing here is simulated: if a step fails the
 * message from the backend is shown and the workflow stops.
 */
type StepState = "idle" | "active" | "done" | "error";
type Step = { id: string; label: string; state: StepState; detail?: string };

const DEMO_SCENARIOS = ["T+1_P-10_D+0_Hrh", "T+2_P-20_D+10_Hrh"];
const STORAGE_PREFIX = "milpa.demo.run25:"; // 25-year window (2001–2025)
const INITIAL: Step[] = [
  { id: "zone", label: "Find the pilot zone", state: "idle" },
  { id: "base", label: "Compute the base run with the scientific engine", state: "idle" },
  { id: "scenarios", label: "Compute synthetic climate scenarios", state: "idle" },
  { id: "open", label: "Open the MVP workspace", state: "idle" },
];

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type JobView = { job_id: string; status: string; result?: Record<string, unknown> | null; error?: { message?: string; code?: string } | null };

async function waitForJob(job: JobView, onTick: (progress: number | null) => void): Promise<JobView> {
  let current = job;
  for (let attempt = 0; attempt < 600; attempt += 1) {
    if (["ok", "failed", "cancelled"].includes(current.status)) return current;
    await wait(800);
    const result = await api.GET("/v1/jobs/{id}", { params: { path: { id: current.job_id } } });
    assertResponse(result.response, result.error);
    current = result.data as unknown as JobView;
    onTick((current as { progress?: number | null }).progress ?? null);
  }
  throw new Error("The job did not finish in time.");
}

function readStored(zoneId: string): string | null {
  try { return window.localStorage.getItem(STORAGE_PREFIX + zoneId); } catch { return null; }
}
function writeStored(zoneId: string, runId: string): void {
  try { window.localStorage.setItem(STORAGE_PREFIX + zoneId, runId); } catch { /* storage unavailable */ }
}

export function DemoScreen() {
  const session = useSession();
  const navigate = useNavigate();
  const access = usePublicAccess(true);
  const [steps, setSteps] = useState<Step[]>(INITIAL);
  const [failure, setFailure] = useState<string | null>(null);
  const started = useRef(false);

  const mark = useCallback((id: string, state: StepState, detail?: string) => {
    setSteps((current) => current.map((step) => (step.id === id ? { ...step, state, detail } : step)));
  }, []);

  const run = useCallback(async () => {
    let active = "zone";
    try {
      mark("zone", "active");
      const zones = await api.GET("/v1/zones");
      assertResponse(zones.response, zones.error);
      // Prefer the pilot cell with the 25-year IMERG series when it is registered; otherwise the first zone.
      const zone = zones.data?.items?.find((item) => item.name === "camotan_jocotan") ?? zones.data?.items?.[0];
      if (!zone) throw new Error("No zone is registered in this installation yet.");
      mark("zone", "done", zone.name);

      active = "base";
      mark("base", "active");
      let runId: string | null = null;
      const stored = readStored(zone.zone_id);
      if (stored) {
        const existing = await api.GET("/v1/runs/{id}", { params: { path: { id: stored } } });
        if (existing.response.ok && existing.data?.status === "ok") {
          // A stored run is only reusable while the engine can still recompute it: if the region
          // configuration or the data changed since it was created, every derived view answers 422
          // (reproducibility guard). Probe one derived view and start a fresh run otherwise.
          const probe = await api.GET("/v1/runs/{id}/summary", {
            params: { path: { id: stored }, query: { scenario: "BASE", adaptation: "none" } },
          });
          if (probe.response.ok) runId = stored;
        }
      }
      if (runId) {
        mark("base", "done", "Reusing the stored base run");
      } else {
        const created = await api.POST("/v1/zones/{id}/runs", {
          params: { path: { id: zone.zone_id }, header: { "Idempotency-Key": `demo-${zone.zone_id}-${Date.now()}` } } as never,
          body: { period_start: "2001-01-01", period_end: "2025-12-31", seed: 42, params: {} },
        });
        assertResponse(created.response, created.error);
        const finished = await waitForJob(created.data as unknown as JobView, () => undefined);
        if (finished.status !== "ok") throw new Error(finished.error?.message ?? `The base run ended as “${finished.status}”.`);
        runId = String(finished.result?.run_id ?? "");
        if (!runId) throw new Error("The base run finished without a run identifier.");
        writeStored(zone.zone_id, runId);
        mark("base", "done", "Base run computed");
      }

      active = "scenarios";
      mark("scenarios", "active");
      const known = await api.GET("/v1/runs/{id}/scenarios", { params: { path: { id: runId } } });
      assertResponse(known.response, known.error);
      const have = new Set((known.data ?? []).map((item) => item.scenario_id));
      if (DEMO_SCENARIOS.every((id) => have.has(id))) {
        mark("scenarios", "done", "Scenarios already computed");
      } else {
        const launched = await api.POST("/v1/runs/{id}/scenarios", {
          params: { path: { id: runId }, header: { "Idempotency-Key": `demo-sc-${runId}-${Date.now()}` } } as never,
          body: { scenario_ids: DEMO_SCENARIOS, adaptation_modes: ["none"] },
        });
        assertResponse(launched.response, launched.error);
        const finished = await waitForJob(launched.data as unknown as JobView, () => undefined);
        if (finished.status !== "ok") throw new Error(finished.error?.message ?? `The scenario job ended as “${finished.status}”.`);
        mark("scenarios", "done", `${DEMO_SCENARIOS.length} synthetic scenarios computed`);
      }

      active = "open";
      mark("open", "active");
      await wait(450);
      mark("open", "done");
      void navigate(`/mvp?runId=${encodeURIComponent(runId)}&zoneId=${encodeURIComponent(zone.zone_id)}&scenarioId=BASE&adaptation=none`);
    } catch (error) {
      mark(active, "error");
      setFailure(error instanceof Error ? error.message : "The demo could not be prepared.");
    }
  }, [mark, navigate]);

  useEffect(() => {
    if (session && !started.current) {
      started.current = true;
      void run();
    }
  }, [session, run]);

  const retry = () => {
    setFailure(null);
    setSteps(INITIAL);
    started.current = true;
    void run();
  };

  return <div className="demo">
    <Link className="demo__brand" to="/"><span className="home-nav__mark"><BrandMark /></span> MILPA RESILIENTE</Link>
    <main className="demo__panel" id="main-content">
      <h1 className="demo__title">Preparing the pilot analysis</h1>
      <p className="demo__lede">This runs the real scientific engine on the curated NASA climate series of the pilot zone, then opens the workspace. No pre-recorded results are used.</p>

      {access === "pending" && <p className="demo__lede" role="status">Opening the public demo…</p>}
      {access === "unavailable" && <div className="demo__error" role="alert">
        <p>The public demo is not enabled on this server. Start it with <code>DEMO_PUBLIC_ACCESS=true</code>.</p>
      </div>}

      {session && <ol className="demo__steps" aria-live="polite">
        {steps.map((step) => <li key={step.id} className={`demo__step demo__step--${step.state}`}>
          <span className="demo__dot" aria-hidden="true" />
          <span><strong>{step.label}</strong>{step.detail && <small>{step.detail}</small>}</span>
          <span className="visually-hidden">{step.state}</span>
        </li>)}
      </ol>}

      {failure && <div className="demo__error" role="alert">
        <p>{failure}</p>
        <button className="home-cta home-cta--ghost" type="button" onClick={retry}>Try again</button>
      </div>}
    </main>
  </div>;
}
