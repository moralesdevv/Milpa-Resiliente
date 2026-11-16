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
