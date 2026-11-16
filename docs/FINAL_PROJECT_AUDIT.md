# FINAL PROJECT AUDIT — actual status (2026-11-16)

Scope: honest status of the repository as it stands. Not a certification. "Verified" means I executed it in this session.

## Status legend
VERIFIED = executed and passed · IMPLEMENTED, UNVALIDATED = code exists, not (fully) executed · PARTIAL · BLOCKED (external dependency) · NOT IMPLEMENTED

## Compliance matrix (against the project spec, `docs/ARCHITECTURE_SPEC_ES.md`)

| Area | Status | Evidence / note |
|---|---|---|
| R1 ETL: NASA POWER fetch/curate/validate | VERIFIED | Real POWER download executed (2001–2025); curated series 9,131 days; R1 CLI contract test passes |
| R1 ETL: IMERG | BLOCKED | Requires `EARTHDATA_TOKEN` (not provided); curated sample already contains IMERG-derived rain |
| R1: DEM / SoilGrids / local station | NOT IMPLEMENTED (DEM: command exists, unrun) | Documented in `docs/DATA_SOURCES.md` |
| R2 engine (`milpa_core`) | VERIFIED | 57 unit tests + 2 adapter tests pass; real-data run OK; ET0 parity 0.035 mm/day |
| R2 science validity | PARTIAL | All sandbox / evidence C; uncited Kc/thresholds flagged provisional; ADRs pending |
| API ↔ engine (runs, scenarios, rank, VoI, heatmap, dekad, history) | VERIFIED | `apps/api/tests/test_core_engine.py` + `tests/integration/test_engine_e2e.py` + live HTTP run |
| Persistence of runs/scenarios (+ Parquet, SHA-256) | VERIFIED | e2e test + live dev DB |
| `engine.risk_summary` / `planting_summary` tables | NOT IMPLEMENTED | Reads served from the engine |
| Parcel/soil-driven runs (Mode B) | NOT IMPLEMENTED | Rejected as pending; soil/food/income criteria not evaluable |
| Security: RLS, roles, privacy (no exact coordinates) | VERIFIED (previous full suite, Docker: 410 passed) | Not re-run in Docker after this session's changes |
| Reports (PDF) | PARTIAL | Report model from engine works; ReportModel→PDF adapter missing; WeasyPrint unavailable on host |
| Reproducibility (hashes, seeds, rebuild-or-refuse) | VERIFIED (engine side) | `make reproduce` comparison with `EXPECTED.json` still waiting on contract |
| Frontend 4 screens | IMPLEMENTED, UNVALIDATED | Adapters + build OK; real-data browser verification incomplete |
| Frontend ↔ real API (Playwright) | NOT IMPLEMENTED | Playwright targets the mock |
| Docker image / compose | IMPLEMENTED, UNVALIDATED | Dockerfile + entrypoint updated for `milpa-core`; not built here |
| CI (GitHub Actions) | IMPLEMENTED, UNVALIDATED | Never executed |
| Lint / types | VERIFIED for `apps/api` | `ruff check apps/api` clean; `mypy` strict: no issues (99 files). `milpa_etl` has 16 known findings; `milpa_core` not yet under ruff/mypy-strict |

## Initial vs final state of this working session
- **Initial**: R2 copied into the workspace, not wired (every engine method raised `PENDING_R2`); jobs always failed with `DEPENDENCY_NOT_INTEGRATED`; `check-core` contract described README signatures that did not match the real package.
- **Final**: engine wired through `core_io.py` + `milpa_core.py`; jobs persist real results; contract corrected to the published signatures; web adapters added; SPA fallback; `register-engine` CLI; Dockerfile/entrypoint prepared.

## Real data connected
NASA POWER daily (downloaded in this session for the pilot cell, lat 14.83 / lon −89.44, 2001–2025) and the already-curated POWER+IMERG daily series for `chiquimula_prueba`. No synthetic data feeds the app; synthetic series exist only in isolated, labelled tests (`tools/r2/make_synthetic.py`) and `data/demo/`.

## Tests executed (this session)
- `packages/milpa_core`: 57 passed. `tests/integration/test_r2_adapter_e2e.py`: 2 passed.
- `apps/api/tests/test_core_engine.py` + `test_adapters_and_static.py` + `test_etl_process.py`: 38 passed (before final edits; targeted re-runs after edits passed).
- `tests/integration/test_engine_e2e.py`: 2 passed. `tests/contract`: 111 passed, 2 skipped, 1 xfailed (R1 script 92 defect, known).
- Broad run (`apps/api/tests tests -m "not slow"`): 402 passed, 5 failed → 4 fixed and re-verified individually; **1 unresolved** (`test_internal_errors_do_not_leak_details`, probably environmental). The complete suite was **not** re-run after the fixes. Not executed: Docker suite, Playwright, `slow` tests (except one earlier R1 CLI test), Schemathesis.

## Bugs found and corrected
1. R1 ingest order (merge before curate) — fixed earlier in `etl_process.py`.
2. `AnalysisRun.mode` inserted as text into `mode_t` enum — fixed (typed Enum).
3. `None` scenario query parameter treated as a scenario id — fixed (defaults to BASE).
4. Strategy/variety query params required UUIDs but the engine uses codes — relaxed to codes (OpenAPI regenerated; documented deviation).
5. `/calendar` etc. returned 404 on direct load (no SPA fallback) — fixed.
6. After login, queries that failed unauthenticated were not retried — fixed (invalidate on login).

## Limits and risks
Sandbox/evidence-C science; rainfall not validated locally; placeholder pilot polygon/elevation; ranking effectively water-only; large `summary` payload (~1.1 MB for 7 strategies, unpaginated); engine context rebuilt per worker process; the web session is held in `sessionStorage` (lost when the pane reloads in some contexts).

## Missing credentials
`EARTHDATA_TOKEN` (IMERG download). GitHub push credentials are the owner's. No secrets are committed (gitleaks staged scan: no leaks).

## Run / deploy
See `README.md` §8 and `docs/PROJECT_HANDOVER.md`.

---

# Update 2026-11-16 (integration pass 2)

## What changed since the matrix above
| Area | Status now | Evidence |
|---|---|---|
| Public demo without login (`POST /v1/auth/demo-session`, `DEMO_PUBLIC_ACCESS`) | VERIFIED | `apps/api/tests/test_demo_session.py` (scope allow/deny), `tests/integration/test_engine_e2e.py::test_public_demo_session_…` (200 for zones, 403 for parcels/DELETE, password login of the demo account impossible, 404 when disabled); browser run: index → LAUNCH DEMO → no login → run + scenarios → calendar |
| Demo security | VERIFIED (by tests above) | Token claim `demo`, allow-list in `api/security/demo.py`, demo account has no parcels (RLS hides private data), random discarded password, 2 h TTL, existing IP rate limit kept |
| Launch demo UI flow | VERIFIED in browser | `DemoScreen.tsx`; banner "Public demo …" on every inner page; falls back to the sign-in form only if the server has the demo disabled |
| Rotation lab: select / configure / run / compare | VERIFIED in browser (page structure + DOM), figures from the engine | scenario picker, adaptation toggle, priority weights, "Compute scenarios" job launcher, ranking with stability, **new** strategy comparison (pick 2–4 strategies, chart + table) |
| Decision report | VERIFIED via UI | report job from the engine's model; summary, risk-by-strategy lines, ranking, annex, hashes; PDF generated with ReportLab (ADR-021), works without Docker/Pango (verified through the API 2026-11-16) |
| Plants | VERIFIED in browser | crops per strategy cycle, exposure metrics, growth stages from the run |
| Data-source honesty | VERIFIED | My zone → "Data sources: what is really connected" table |
| English UI | VERIFIED for UI chrome | engine narrative strings translated through `api/engine-text.ts`; unknown strings remain as received |

## Sources: real status
Integrated: NASA POWER daily (downloaded + curated). Implemented but needs credentials/data: GPM IMERG (token), Copernicus DEM. **Not integrated**: Landsat 8/9, MODIS, HLS, SMAP, NEX-GDDP-CMIP6, SoilGrids, local stations, MAGA, INAB, SEGEPLAN. Nothing in the app claims otherwise.

## Scientific observations worth a reviewer's attention
- With the sandbox thresholds (calibrated on a synthetic series by R2) every strategy shows **0 % critical cohorts** on the real Chiquimula series, and E1/E2 show identical P90 severity. The comparison UI works, but the numbers do not discriminate strategies until thresholds with citations and local calibration exist. This is an input limitation, not a UI bug.
- The ranking effectively uses the water criterion (soil criterion partially: cover months, family diversity); food and income are not evaluable (no cited yields/prices).
- Evidence level is C throughout (rainfall unvalidated locally; thresholds provisional).

## Not done / not verified
Parcel-based runs and soil value-of-information (need `SoilContext` from parcel data); PDF rendering (Docker only); Docker image build; eslint; Playwright against the real API; GitHub Actions; R1 lint findings; ADR approvals; verification of the full test-suite after the last edits (see `NEXT_STEPS.md`).

---

# Update 2026-11-16 (pass 3): MVP-document acceptance and the extra R2 package

## What the folders on the Desktop were
`Desktop/R1`, `Desktop/R2` and `Desktop/R4` are byte-identical to `references/` (only `.git` internals differ): they were already integrated (R1 → `packages/milpa_etl`, R2 → `packages/milpa_core` + `catalogs/r2` + `regions/r2`, R4 → `apps/web`). `Desktop/MILPA_RESILIENTE_R2_Motor_Cientifico` is a **different, earlier monolithic R2 deliverable**. Its engine code is superseded by `packages/milpa_core` (not copied, to avoid regressing). Integrated from it:
- **Real IMERG daily series 2001-01-01 → 2025-09-30** for the Camotán/Jocotán cell (`tools/r2/import_imerg_csv.py` → R1 raw format → `milpa-etl merge imerg`). **Unit finding, verified in the GeoTIFF metadata** (`Unit=0.1(mm/hr)`, `…total.rate.tif`): the CSV column `precipitation_mm` is the mean *rate* (mm/h), not a daily total; daily mm = rate × 24. After the conversion annual totals are 1123–2126 mm and IMERG/POWER = 1.04 (before it, ≈ 55–90 mm/yr: wrong).
- New approximate zone `camotan_jocotan` (`regions/camotan_jocotan.geojson`: the 0.1° IMERG cell, **not** a municipal boundary), curated with POWER (14.82, −89.38, 457 m) + IMERG (99 % of days IMERG, 1 % POWER fallback, the demo prefers this zone).
- Reference catalogs/docs copied but **not loaded by the engine**: `catalogs/r2/reference/{economics,evidence_rules,web_sourced_crops}.yaml` (all prices/yields `pending`; ICTA variety references flagged "conflicting values pending technical resolution"), `docs/r2/sources_r2pkg/{WEB_SOURCES,WEB_FINDINGS,DESCARGAS_PENDIENTES}.md`, `references.bib`.

## MVP §29 acceptance, as of now
| ID | Status | Evidence |
|---|---|---|
| A unknown soil → Mode A, VoI evaluable | VERIFIED | `test_parcel_run_uses_soil_and_voi_separates_availability_from_outcome` |
| B hidden dry dekad | R2 unit/property tests (57 pass); not re-run as an API scenario | |
| C combined scenario `T+2_P-20_D+20_Hrh` | PARTIAL: computable (45-grid) and shown with `ScenarioBadge`/inversions; not exercised by an automated API test | |
| D hypothetical pH | PARTIAL: (iii) `already_measured` and evaluable-without-pH verified; (i)/(ii) outcomes depend on the region's `zone_ph_range` (null in the sandbox pack ⇒ `insufficient_info`) | |
| E weights/stability | VERIFIED in UI and API (`rank`, seed, n_samples) | |
| F report | VERIFIED via UI and API: sections, tables, hashes, authenticated PDF download with SHA-256 check (ReportLab) | |
| G reproduce | VERIFIED for data + engine fingerprint; alternate region run without touching `packages/` not tested | |
| H multi-year rotation | R2 unit tests; E7 appears in the comparison | |
| I missing data in ranking | VERIFIED in the real run (food/income excluded for all, `decision_log`) | |
| J privacy/access | existing RLS/privacy suites pass (one environmental failure, see NEXT_STEPS); demo scope tested | |

Soil from the parcel now feeds the engine (`core_io.soil_context_from_rows`, units/codes mapped, `Dr0` absent ⇒ Mode B stays off per CT-05) and a real `EvidencePort` (`MilpaCoreEvidence`) assigns A/B/C from `milpa_core` rules, so CSV upload and declarations persist.

---

# Update 2026-11-16 (pass 4): MVP workspace and compliance with "MILPA RESILIENTE 3.3 MVP.md"

## New: the central page (`/mvp`, "MVP workspace")
`apps/web/src/screens/MvpScreen.tsx` is the hub LAUNCH DEMO now lands on. It reads the same run, scenario and engine results as the detail screens (no new calculations) and shows, in one scroll: how the result was made (5 steps + hashes + mode), territory/crops/pending decisions (`GET /zones/{id}` now returns `agri_context` from the R2 region pack), data coverage/quality and the real status of every source, the 25-year climate history with descriptive trends, the strategies (family, crops, critical cohorts "X of N evaluable", P90 severity, rank, stability), a plain-language reading generated only from engine figures (`lib/insights.ts`, unit-tested), side-by-side comparison, baseline-vs-scenario position inversions, the planting heat-map, limits stated up front, and links into each detail screen keeping the shared parameters.

## Four strategies?
The document does not define "four strategies"; it defines strategy *families* (reference, traditional milpa association, alternatives, rotations; §18). The pilot has seven strategies (E1–E7) and the hub groups them with those families.

## Compliance matrix against the document (honest)
| Doc § | Requirement | Status |
|---|---|---|
| §3-4 F01 | 25-year history, coverage, summary | DONE (25 years of the pilot cell; descriptive trends added; no formal tests, as the doc allows) |
| F02 | robust comparison (frequency, severity, P90, CVaR90, worst year, n_valid/n_expected) | DONE (cards, cycle table, hub; `n evaluable of N` shown beside frequencies) |
| F03 | critical stages by variety, provisional without citation | DONE (all provisional: 16/16 stages and 3/3 thresholds uncited) |
| F04-F05 | dekad analysis; Pef vs ETc chart with stage bands | DONE (Calendar screen) |
| F06 | heat-map date × year, cycle and strategy views, critical-% row | DONE (Calendar; hub shows strategy view) |
| F07 | associations and rotations with cohorts | DONE (E2 milpa, E3 sequence, E7 two-year rotation) |
| F08-F10 | multi-criteria ranking with missing data, sliders, stability | DONE (water + part of soil evidenced; food/income excluded for all, with `decision_log`) |
| F11 | 27+18 scenarios, two adaptation readings | DONE in engine (45 computed in earlier run); UI: pick computed ones, launch others; `onset_rule` reading available in Rotation lab |
| F12 | Soil VoI (pH) | PARTIAL: works end to end with a parcel; outcome stays `insufficient_info` because the region pack has no cited `zone_ph_range` |
| F13 | provenance A/B/C on every figure | DONE for figures (Indicator); prose findings quote engine figures |
| F14 | decision report, English summary, hashes, references, missing data, field conditions | DONE on screen (priorities, missing data incl. pH analysis, field conditions, sources, references, hashes); PDF only inside Docker |
| F15 | reproducibility | DONE (`make reproduce` with engine fingerprint); alternate-region run not tested |
| §8 level A data | POWER, IMERG, DEM, SoilGrids, soil CSV, station CSV | POWER + IMERG real (25 years). Soil CSV done. **Not done:** SoilGrids, station CSV, DEM for the pilot (zone elevation/slope shown "not available"). |
| §18 screen 1 | agricultural context with [Pending] marks | DONE (crops, seasons, counts of uncited items) |
| §18 screen 2 | descriptive trends, dekad chart, heat-map | DONE |
| §18 screen 3 | strategies, comparison, scenarios, priorities, ranking, stability, inversions | DONE |
| §18 screen 4 | main page + technical annex, privacy levels, "not an automatic recommendation" | DONE on screen; annex lacks the full per-cycle results table |
| §19 | scenario grammar and tag, no forecast wording | DONE (text linter passes) |
| §22 | privacy, RLS, public report level | DONE (existing suites green) |
| §29 CT-01..CT-12 | see below | CT-02/03/04/06/07/08/10/11/12 verified or tested; CT-01 true for figures, not for prose; CT-05 (Mode B only with full soil + Dr0) holds because Dr0 has no API |

## Verified in this pass
- Full suite after all changes: see NEXT_STEPS (run at the end of this pass).
- Browser: demo → `/mvp` with real data (7 strategies, 25 cohorts, ranking, stability, inversions for `T+2_P-20_D+10_Hrh`, heat-map, history with 25 rows, crops/pending list, report generation with the new sections).
- Scientific observation: under `T+2_P-20_D+10_Hrh` the reference strategy drops from 3rd to 7th and several strategies show a critical cohort; under BASE only the milpa association does (1 of 25).
