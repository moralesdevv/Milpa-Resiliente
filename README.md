# MILPA RESILIENTE

**Climate-resilient planting and rotation decisions for smallholder maize–bean (*milpa*) farmers in Guatemala's Dry Corridor — built on NASA Earth observations.**

> NASA Space Apps Challenge submission · Status: **working MVP, sandbox mode** · All scientific results are *provisional* (evidence level C) until local validation — see [Limitations](#limitations-and-honest-status).

---

## 1. The problem

Smallholder farmers in Guatemala's *Corredor Seco* (Dry Corridor) plant maize, beans and sorghum on rain-fed land. The rainy season is bimodal — a *primera* (May–June), a mid-summer dry spell (*canícula*, July–August) and a *postrera* (September–October) — and its onset, length and intensity are shifting. A bad planting date or crop sequence can cost a household's entire food supply.

Technicians and farmers need an answer to a practical question: **"Given the last 25 years of climate here, when and what should we plant — and how sure are we?"**

## 2. What MILPA RESILIENTE does

It compares **planting-date and crop-rotation strategies** against 25 years of real satellite/reanalysis climate and shows, for each strategy:

- the **frequency and severity of water exposure** during critical crop stages (dekad-by-dekad, 10-day steps);
- a **planting-date heat-map** (date × year) with consistent planting windows;
- a **multi-criteria ranking** (water, soil, food, income) with a **stability test** over perturbed weights;
- **45 synthetic climate scenarios** (ΔT 0/+1/+2 °C, precipitation ×1.0/0.9/0.8, onset delay 0/10/20 days, two humidity assumptions) — always labelled *synthetic scenario, not a forecast*;
- the **provenance of every number** (source, method, evidence level A/B/C, limitations).

Four screens: **My zone**, **How the calendar changed**, **Rotation lab**, **Decision report**.

Honesty is a design rule: missing data is shown as *not evaluable*, never silently filled; a criterion without evidence never wins the ranking.

## 3. NASA data used

| Dataset | Role | Status in this repo |
|---|---|---|
| **NASA POWER** (daily, AG community: T2M_MAX/MIN, T2MDEW, RH2M, WS2M, ALLSKY_SFC_SW_DWN, PRECTOTCORR; MERRA-2 / CERES) | Base climate 2001–2025, ET0 inputs, fallback precipitation | **Implemented and used** (`milpa-etl fetch power`, no key required) |
| **GPM IMERG Final Run V07** (`GPM_3IMERGDF`, 0.1°) | Primary precipitation where available (2021 →) | **Implemented** in the ETL; needs an Earthdata token (`EARTHDATA_TOKEN`, never stored in the repo) |
| Copernicus GLO-30 DEM (ESA, not NASA) | Zone elevation/slope | ETL command exists (`fetch dem`); pilot zone elevation is still a placeholder |
| SoilGrids (ISRIC), local weather stations, MODIS/HLS/SMAP/NEX-GDDP, Guatemalan agency data | Soil, validation, vegetation, projections | **Not implemented** (documented as such; nothing is faked) |

Pilot zone in the demo database: `chiquimula_prueba` (Chiquimula department; **approximate test polygon**). The curated series covers 2001-01-01 → 2025-12-31 (9,131 days). Known data caveats are listed in [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) (e.g. 81 % of days use POWER rainfall because IMERG starts in 2021; 9 POWER outlier days).

## 4. Architecture

A deliberately simple **modular monolith** (two services in production: `db`, `app`).

```
 NASA POWER / IMERG ──► R1  milpa_etl      fetch → curate → validate → merge  ──► Parquet (curated daily series)
                                                                                      │
 catalogs/r2 + regions/r2 (YAML, versioned) ──────────────────────────────────────────┤
                                                                                      ▼
                        R2  milpa_core   pure scientific library (no I/O): ET0 FAO-56, effective rain,
                                          exposure / root-zone balance, cohorts, risk, scenarios,
                                          ranking, stability, soil value-of-information
                                                                                      ▲
 React + ECharts + Leaflet  ◄──── R3  FastAPI  ◄── adapters (core_io, milpa_core) ───┘
   (R4, 4 screens)               auth · RLS · jobs · reports        │
                                                                    ▼
                                                        PostgreSQL 16 + PostGIS (+ Parquet results)
```

- **R1 – `packages/milpa_etl`**: data acquisition and curation, SHA-256 provenance manifests.
- **R2 – `packages/milpa_core`**: the science. No file/DB/HTTP access; deterministic and seeded.
- **R3 – `apps/api`**: FastAPI + SQLAlchemy 2 + Alembic. *Never* recomputes science: it loads inputs (`adapters/core_io.py`), delegates to the engine (`adapters/milpa_core.py`), persists runs (`engine.analysis_run`, `engine.scenario_run`, Parquet + SHA-256) and serves results.
- **R4 – `apps/web`**: React 18, Vite, ECharts, Leaflet, i18n (ES/EN). `src/api/r2-adapters.ts` maps engine payloads to view models without altering values.
- Long computations run as **jobs** (process pool, state in PostgreSQL). No Redis/Celery/Dask by design.

## 5. Scientific methodology (summary)

Full details: [`docs/r2/METHODS.md`](docs/r2/METHODS.md).

- **ET0**: FAO-56 Penman–Monteith from POWER variables (vapour pressure from dew point, with RH sensitivity). The engine's ET0 was compared with R1's independent implementation over 1,826 days: **mean absolute difference 0.035 mm/day**.
- **Two modes, never mixed**: *climate exposure indicator* (always available) and *root-zone water balance* (only with sufficient soil data). The pilot currently runs in exposure mode — it is **not** a soil-moisture deficit.
- **Effective precipitation** per dekad with several methods and a sensitivity band; **critical-stage thresholds** with a citation requirement (uncited thresholds are flagged provisional).
- **Cohorts**: multi-year rotations are evaluated from every possible starting year; results by cycle and by full strategy.
- **Risk metrics**: critical frequency, median / P90 / CVaR90 severity, worst year, tail ratio.
- **Ranking**: weighted multi-criteria on the common-support criteria only; **stability** by Dirichlet/ball sampling of weights (seeded).
- **Reproducibility**: fixed seeds, SHA-256 hashes of data, region config and catalogs stored with each run; the engine rebuilds a run from its hashes and **refuses** if inputs changed.

## 6. Security and privacy

- JWT auth, roles (`agricultor`, `tecnico`, `admin`), Argon2 password hashing, rate limiting.
- **PostgreSQL Row-Level Security**; per-request `SET LOCAL app.user_id`; the app role is not owner and has no `BYPASSRLS`; migration credentials are dropped before the API starts.
- **No exact parcel coordinates stored** — only a generalised display geometry (≥ 1 km grid).
- Consent-gated analysis; tokens/passwords never logged; secrets only via environment (`.env` is git-ignored; see `.env.example`).
- Automated checks: gitleaks, privacy-leak tests, RLS tests, OpenAPI contract tests.

## 7. Technology

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL 16/PostGIS · pandas/NumPy/PyArrow · WeasyPrint (PDF) · uv workspace · React 18 · TypeScript · Vite · ECharts · Leaflet · Playwright/Vitest · pytest · Hypothesis · Schemathesis · Ruff · strict mypy · Docker Compose.

## 8. Quick start

Requirements: Docker (recommended) or Python 3.12 + [uv](https://docs.astral.sh/uv/) + PostgreSQL 16/PostGIS, Node 20+.

```bash
cp .env.example .env            # set POSTGRES_PASSWORD, APP_DB_PASSWORD, JWT_SECRET (>= 32 chars)
docker compose up --build       # db + app (migrations and engine catalog registration run on start)
# open http://127.0.0.1:8000
```

Local development without Docker (what was used for the demo run):

```bash
uv sync --all-packages --all-groups
cd apps/api && alembic upgrade head && cd ../..
python -m api.cli register-engine          # R2 catalog + 45 scenario definitions (owner role)
milpa-etl fetch power --zone chiquimula_prueba --lat 14.83 --lon -89.44 --start 20010101 --end 20251231
milpa-etl register zone --zone chiquimula_prueba --geojson regions/chiquimula_prueba.geojson \
          --region-config regions/pilot_corredor_seco.yaml
python -m api.cli create-user --email you@example.org --role tecnico
uvicorn --factory api.main:create_app --port 8000
cd apps/web && npm ci && npm run build
```

Then `POST /v1/zones/{zone_id}/runs` (body: `period_start`, `period_end`, `seed`) creates a base run as a job; `POST /v1/runs/{id}/scenarios` computes the 45-scenario grid. Tests: `make test-docker` or `pytest apps/api/tests tests -m "not slow"`.

## 9. Results on the real pilot data (sandbox)

From an actual run on `chiquimula_prueba` (2021–2025 window, seed 42): base run ≈ 3 s; all **45 scenarios** computed and persisted; 7 strategies (E1 reference maize … E7 two-year rotation) evaluated over 422 cycle results; ranking stable under weight perturbation **but based on the water criterion only**, because soil, food and income criteria lack evidence in the sandbox catalogs (they are reported as *not evaluable*).

## 10. Scalability

The engine is vectorised NumPy over daily series; scenario grids are independent and parallelise per process. Regions are data, not code: add a region pack + catalog (`docs/ADD_A_REGION.md`). Results are Parquet with SHA-256, so history is reusable without recomputation. Larger deployments can move the object store and job pool out of the monolith without changing contracts.

## 11. Limitations and honest status

- **Everything is sandbox / evidence C.** Thresholds are calibrated on a synthetic series and Kc values are FAO-56 candidates without per-crop citations; several decisions marked *[Proposed R2]* need agronomic confirmation.
- Rainfall is satellite/reanalysis, **not validated against a local station**.
- The pilot polygon, elevation and slope are placeholders; SoilGrids/stations/other NASA products are not integrated.
- Runs with a **parcel** (declared/measured soil) are not wired to the engine yet; soil, food and income criteria are therefore not evaluable.
- The web adapters for the real engine payloads are built and type-checked, but the four screens have **not been fully verified end-to-end in a browser** yet.
- Docker image with the engine, GitHub Actions and Playwright-against-real-API have not been run. See [`docs/FINAL_PROJECT_AUDIT.md`](docs/FINAL_PROJECT_AUDIT.md).

## 12. Impact

A decision-support tool that makes 25 years of NASA climate usable at farm level, explains its uncertainty, and tells the farmer what is *not* known — aimed at reducing crop-failure risk and food insecurity in one of the most climate-vulnerable regions of Central America.

## 13. Repository map

| Path | Content |
|---|---|
| `apps/api` | R3 backend (FastAPI), migrations, tests |
| `apps/web` | R4 frontend |
| `packages/milpa_core` | R2 scientific engine |
| `packages/milpa_etl` | R1 data pipeline |
| `catalogs/`, `regions/` | Versioned catalogs and region packs (`r2/` = engine inputs) |
| `docs/` | Architecture, API, security, methods, audits, handover |
| `docs/ARCHITECTURE_SPEC_ES.md` | Original full technical specification (Spanish, source of truth) |

## 14. License and credits

Data: NASA POWER, NASA GES DISC (GPM IMERG) — cite the sources per their terms; real NASA data are not redistributed, only download scripts and hashes. Code license: to be defined by the team.
