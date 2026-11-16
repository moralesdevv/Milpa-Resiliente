# NEXT STEPS — where development stopped (2026-11-16)

Read this first, then `docs/PROJECT_HANDOVER.md` and `docs/FINAL_PROJECT_AUDIT.md`.

## Where I stopped (read the MVP workspace first)
`/mvp` is now the central page (LAUNCH DEMO lands there): evidence and sources, 25-year climate, strategies with a plain-language reading built from engine figures, comparison, baseline-vs-scenario inversions, planting calendar, limits, links into every detail screen. See `docs/FINAL_PROJECT_AUDIT.md` ("pass 4") for the compliance matrix against the MVP document. Still missing against the document: SoilGrids, station CSV and DEM ingestion (zone elevation/slope are shown as unavailable), a cited `zone_ph_range` (so the pH value-of-information stays `insufficient_info`), per-cycle results table in the report annex, Playwright against the real API, a tested alternate region.

## (previous status)
The app runs end to end on real NASA data (POWER + IMERG-derived series for the test polygon `chiquimula_prueba`):
**index → LAUNCH DEMO (no login) → real base run + synthetic scenarios → calendar, rotation lab (compare strategies), plants, report, my zone.** The index was not touched in this pass.

Verified by execution: demo-session scope tests, e2e integration tests (engine + PostgreSQL + jobs + demo), browser walk-through of the demo, report generation, strategy comparison, source-status table. Not verified: see "Open problems".

Run it locally (what I used):
```bash
# DB: docker container milpa-test-db on :55432, database milpa_dev (migrated, zone + R2 catalog + demo user registered)
export DATABASE_URL="postgresql+psycopg://milpa_app:app_test_only@127.0.0.1:55432/milpa_dev"
export JWT_SECRET="<32+ chars>" DATA_DIR=./data DEMO_PUBLIC_ACCESS=true
.venv/Scripts/python.exe -m uvicorn --factory api.main:create_app --port 8000   # serves apps/web/dist
cd apps/web && npx vite build                                                   # rebuild the frontend
```
Fresh install: `docker compose up --build` with `DEMO_PUBLIC_ACCESS=true` in `.env` (entrypoint runs migrations, `register-engine`, `create-demo-user`). **The Docker image has not been built after the `milpa-core` edits — do this first.**

## Added in the last pass (2026-11-16, MVP-document pass)
- Parcel runs: `parcel_id` is accepted; the parcel's soil (RLS-respecting snapshot) feeds `SoilContext` and is stored in `analysis_run.params.soil`; soil upload/declaration persist through the real `MilpaCoreEvidence`. Mode B still needs a declared `Dr0` (no API for it yet).
- 25-year analysis: the run `period` now sets the engine window (the sandbox region file says 2021–2025 for its synthetic tests). The demo requests 2001–2025.
- Extra R2 package integrated (see `docs/FINAL_PROJECT_AUDIT.md`, "pass 3"): real IMERG 2001–2025-09 for zone `camotan_jocotan`, with the ×24 unit correction. **Register the zone in any new database:** `milpa-etl register zone --zone camotan_jocotan --geojson regions/camotan_jocotan.geojson --region-config regions/pilot_corredor_seco.yaml`, and keep `data/curated/camotan_jocotan/` (git-ignored; regenerate with `fetch power` → `curate` → `tools/r2/import_imerg_csv.py` → `merge imerg`, needing the CSV from `Desktop/MILPA_RESILIENTE_R2_Motor_Cientifico/data/curated/imerg/`).

## What to do to finish (priority order)
1. **Push to GitHub** (nothing from the last two passes is committed). Remote `origin` has an unrelated "Initial commit"; use `git pull origin main --allow-unrelated-histories`, keep our `README.md`, never force-push. `apps/web/dist` and `tsconfig.tsbuildinfo` are tracked — consider `git rm -r --cached` them.
2. **Test status (last full run, 2026-11-16, end of pass 4):** 437 passed, 12 skipped, 1 xfailed (the known R1 script-92 defect), 0 failed; one boundary test failed on a report sentence and was fixed and re-run (contract + privacy + reports: 131 passed). The old privacy failure was caused by the host's compiled frontend; tests no longer depend on it (`testkit/app.py`). Web: vitest 31 passed, eslint clean, text linter passes. Not run: Playwright against the real API, GitHub Actions, `slow` tests, compose smoke test (the runtime image does build).
3. **Soil / parcel flow (R3 spec "SoilContext")**: `run_base_analysis` rejects `parcel_id`. Build `SoilContext` from declared/measured soil (`soil.*` tables) so Mode B (root-zone balance), soil criterion and Soil VoI can run. The demo scope intentionally forbids parcels/soil-voi.
4. **Agronomic inputs (blocks scientific usefulness)**: with sandbox thresholds every strategy shows 0 % critical cohorts on the real series and E1/E2 have identical P90. Needs cited thresholds, Kc, pH tolerances, reference yields, prices, food composition (`catalogs/r2/*.yaml`; every `citation: null` is a gap) and local calibration; then ADRs 003, 007, 009, 010, 015–018.
5. **PDF**: generated with ReportLab (pure Python, ADR-021), so it works on Windows without Docker or Pango; verified end to end through the API (job, `GET /v1/reports/{id}/pdf`, SHA-256 matches). WeasyPrint is now an optional extra (`html-pdf`); its HTML-path tests are skipped without Pango.
6. **Remaining sources** (documented, none integrated): Landsat 8/9, MODIS, HLS, SMAP, NEX-GDDP-CMIP6, SoilGrids, local stations, MAGA, INAB, SEGEPLAN. Each needs an ETL connector + provenance rows; do not claim them until they exist. IMERG download needs `EARTHDATA_TOKEN`.
7. **Frontend polish / checks not run**: `npm run lint`, Playwright against the real API (currently mock only), accessibility pass on the new screens, `prefers-reduced-motion` check on inner pages, strings from the engine that are not in `apps/web/src/api/engine-text.ts` still appear in Spanish.
8. **Rotation lab limits**: users can pick scenario, adaptation reading, priority weights, compute scenarios and compare 2–4 strategies. Management variables (planting windows, varieties, associations) are defined by the region pack/strategy YAML (`regions/r2/*.strategies.yaml`), not editable in the UI — adding strategy editing needs a validated authoring flow (R2 `validate_strategy`) and an ADR.
9. **Clarify "R1–R4"**: in this repo R1 = data/ETL (`milpa_etl`), R2 = scientific engine (`milpa_core`), R3 = backend (`apps/api`), R4 = frontend (`apps/web`) — they are work packages, not four strategies. The pilot compares **seven** strategies (E1–E7). If "four strategies" is a different requirement, point to the document section that defines it.
10. Housekeeping: `mypy --strict` on `milpa_core` went from 183 to 113 errors (generic type arguments and numeric-kernel annotations done; what is left is Optional narrowing in exposure/rootzone/risk/criteria/ranking/strategy/scenarios, `_ind`/`_p` helper signatures in dto/risk/facade). It is typing only, but each Optional needs a reading of the code; (earlier note: 183 errors (43 missing annotations, 35 untyped calls, 34 generic args, ~49 real Optional/arg-type issues to review — fix without changing the science); `npm audit` reports 3 moderate `react-router` 6.x advisories (the fix is the v7 upgrade, a breaking change); R1 lint (F/B classes) is clean, style rules are not enforced on `packages/`. Done in this pass: R1 findings, `pip-audit` (clean), enum parity R2↔SQL test, `make reproduce` with the engine fingerprint (`data/demo/EXPECTED_ENGINE.json`), Makefile `run-base`/`scenarios`/`test-science` unblocked, ADR-020, stale docs refreshed.

## Open problems / things not verified
- Full test suite after the last edits (see item 2). Docker build, eslint, Playwright, GitHub Actions: not run.
- There is no sign-in in the interface (not valid for the challenge). The app obtains the scope-limited public demo session by itself (`apps/web/src/api/public-access.ts`) and renews it before it expires (2 h); the server must run with `DEMO_PUBLIC_ACCESS=true`, otherwise every in-app page says public access is not enabled. The `/v1/auth/login` API endpoint still exists (it is part of the specified contract and its tests) but nothing in the UI uses it.
- Local rate limit: `scripts/start_local.ps1` sets `RATE_LIMIT_PER_MIN=1200`; the default (120 per IP) is exceeded by normal browsing of the workspace.
- **Build blocker not caused by this change:** `apps/web/src/components/zone/ZoneMap.tsx` (edited outside this session) imports `../../../../regions/jocotan_chiquimula_boundary.geojson`, which resolves to `apps/regions/…`; it needs one more `../` (the file is at repo-root `regions/`). `vite build` fails until that path is fixed, so the last successful build (served from `apps/web/dist`) is what is running.
- The demo shares one zone; anyone can create runs in it (rate limited per IP). Consider a per-session quota and periodic cleanup of demo runs.
- Real-data caveat: IMERG-derived rain is 19 % of days (2021→); POWER fills the rest; no local station validation (evidence C).

## Key files
`apps/api/src/api/{adapters/{core_io,milpa_core}.py, security/demo.py, jobs/handlers/{engine_jobs,reports}.py, reports/from_engine.py, cli.py}` · `apps/web/src/{screens/*, api/{queries,r2-adapters,engine-text}.ts, components/scenario/StrategyCompare.tsx}` · `tests/integration/test_engine_e2e.py` · `apps/api/tests/{test_core_engine,test_demo_session}.py`.

## Arranque rápido del MVP en el navegador (sin Docker)
`powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1` — levanta el contenedor `milpa-test-db`, arranca la API con la demo pública activada y abre http://127.0.0.1:8000. Docker Compose/PDF son opcionales para este MVP (el PDF solo sale dentro de Docker; en local el informe se muestra en pantalla).
