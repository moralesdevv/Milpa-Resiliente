# PROJECT HANDOVER — where development stopped

Date: 2026-11-16 · Repo root: `milpa-resiliente` · Branch `main` · Local commit `8019365` ("chore: upload current MILPA RESILIENTE project state"), **not pushed**.

## Git situation (read first)
- Remote `origin` = `https://github.com/moralesdevv/Milpa-Resiliente.git` was added locally.
- The remote `main` already contains one unrelated commit (`a41109f` "Initial commit", only a stub `README.md`). Histories do not share an ancestor, so a plain push is rejected. Do **not** force-push. Safe path:
  ```bash
  git pull origin main --allow-unrelated-histories   # conflict only in README.md
  git checkout --ours README.md && git add README.md  # keep the project README
  git commit --no-edit && git push origin main
  ```
- After the commit I added (uncommitted): hardened `.gitignore`, `docs/ARCHITECTURE_SPEC_ES.md` (copy of the original Spanish README/spec, source of truth), new English `README.md`, this file, `docs/FINAL_PROJECT_AUDIT.md`, and untracked `apps/web/test-results/`. Commit them before pushing.
- gitleaks (staged scan) found **no leaks**. `.env`, `data/raw`, `data/curated`, `references/`, `node_modules`, `.venv` are ignored.

## What works (verified by execution)
- `milpa_core` (R2) integrated: 57 unit tests + 2 adapter tests pass; engine runs on the **real curated series** (1,826 days, 0 % missing) in ~1.6 s; ET0 vs R1: 0.035 mm/day mean abs. difference.
- API → engine wiring (`apps/api/src/api/adapters/core_io.py`, `milpa_core.py`): base run, 45-scenario grid, rank + stability, soil VoI (without soil → no invented value), report model, heatmap, dekad chart (filterable by strategy/cohort/cycle/date), climate history (annual totals).
- Persistence: jobs write `engine.analysis_run`, `engine.scenario_run`, Parquet + SHA-256 under `DATA_DIR/results/<run_id>/<scenario>/<adaptation>/`.
- `python -m api.cli register-engine` (owner role, idempotent) registers the R2 catalog release and 45 `engine.scenario_def` rows; the Docker entrypoint calls it.
- End-to-end integration tests `tests/integration/test_engine_e2e.py` (real PostgreSQL + real engine, synthetic *labelled* series) pass.
- Live run against a dev DB (`milpa_dev` in the test container, port 55432) with **real NASA POWER/IMERG curated data** for `chiquimula_prueba`: base + 45 scenarios computed through the HTTP API; summary/heatmap/dekad/rank endpoints respond 200.
- Frontend: `apps/web/src/api/r2-adapters.ts` maps real engine payloads to the existing view models; TypeScript compiles and `vite build` succeeds. SPA fallback added in `apps/api/src/api/main.py` (direct URLs like `/calendar` work).
- Fixed along the way: R1 ingest order (curate before IMERG merge), `mode` enum cast in `AnalysisRun`, query-invalidation after login.

## What is incomplete / unverified
1. **Screens not verified in a browser end-to-end.** Login works; after a full page load the session (sessionStorage) was lost in the preview pane, and I did not finish checking Heatmap/DekadChart/RiskCards/Rotation lab/Report with real data. Playwright still runs against the mock only.
2. **Full test suite not re-run after the last edits.** Last full run (`-m "not slow"`): 402 passed, 5 failed. Four were caused by the integration and fixed (re-run targeted: pass). The fifth, `tests/privacy/test_privacy_leaks.py::test_internal_errors_do_not_leak_details`, returns 404 because `apps/web/dist` exists on this host and the static mount catches the late-added test route — *likely environmental, not verified*.
3. **Reports (PDF)**: `build_report` returns R2's model, but the handler `api/jobs/handlers/reports.py` still raises `DependencyNotIntegrated` (ReportModel → `ReportInput` adapter missing). WeasyPrint/Pango is unavailable on this host (use Docker).
4. **Parcel-based runs** (`parcel_id`) are rejected as PENDING: building `SoilContext` from declared/measured soil is not wired → soil/food/income criteria remain *not evaluable*; ranking uses water only.
5. `engine.risk_summary` / `planting_summary` tables are not populated (reads come from the engine, not these tables).
6. A run rebuilt in another process re-derives its context from the curated series and **refuses** if hashes changed (by design). The base run holds no in-process cache across worker processes (recompute ≈ 2–3 s).
7. Docker image with `milpa-core` (Dockerfile/entrypoint edited) **not built**; `infra/scripts/smoke-compose.sh` never completed; GitHub Actions never run.
8. Frontend does not list runs (no endpoint); the UI asks for a `run_id`. Thresholds panel in the heatmap is empty (R2 does not publish `thresholds_used` in the heatmap payload).
9. Data: IMERG needs `EARTHDATA_TOKEN` (not in repo); SoilGrids, stations, DEM for the pilot zone, other NASA products not implemented. Pilot polygon is a test polygon.
10. Scientific status: everything is `sandbox`/evidence C; **[Proposed R2]** decisions in `docs/r2/METHODS.md` need agronomic ADRs; pending ADRs 003, 007, 009, 010, 015–018.
11. `packages/milpa_etl` has 16 un-fixed lint findings (see `docs/CONTINUAR_AQUI.md` §D); ruff/mypy-strict not yet extended to `milpa_core`.
12. Docs `DATABASE.md`, `DEPLOYMENT.md` (stop at migration 0013; 0014 exists), `API.md`, `JOBS.md`, `HANDOFF.md` are partly outdated.

## What remains to finish (priority order)
1. Push (see above); rebuild the Docker image; `docker compose up`; run `register-engine` + zone registration; smoke test.
2. Browser-verify the four screens against the real API (log in → `/calendar?runId=…&scenarioId=BASE`), fix remaining adapter mismatches (`RiskCards`, Rotation lab, Report screen), then Playwright against the real API.
3. Wire `SoilContext` from parcel soil; add the report model → PDF adapter.
4. Resolve the privacy test failure (check with `apps/web/dist` absent).
5. Agronomic review of thresholds/Kc/ph tolerances; validate rainfall with a local station.
6. Extend ruff/mypy-strict to `milpa_core`; fix R1 lint findings; run `pip-audit` / `npm audit`.

## How to run what exists
See `README.md` §8. Dev credentials created locally (users `tecnico@milpa.local`, `admin@milpa.local`) live only in the local dev DB, not in the repo. Scratch dev DB: `docker exec milpa-test-db psql -U postgres -d milpa_dev`. Useful files: `docs/CONTINUAR_AQUI.md` (previous handover), `docs/r2/METHODS.md`, `tools/r2/r2_run.py` (CLI recipe of the engine).
