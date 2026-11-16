# MILPA RESILIENTE — automatización de R3. Requiere GNU make (Linux/macOS/WSL/Git-Bash con make).
# R1 (packages/milpa_etl) y R4 (apps/web) están integrados. Lo que depende de R2 (milpa_core, aún no
# entregado) NO se simula: falla con código != 0 indicando qué falta (spec R3 §20).
SHELL := /bin/sh
UV    ?= uv
PY    := $(UV) run --all-packages python
ENV_FILE ?= .env

.DEFAULT_GOAL := help
.PHONY: help setup lint format typecheck test test-unit test-contract test-integration test-docker \
        test-science test-e2e db-up db-down db-migrate seed data run-base scenarios up demo build \
        reproduce report openapi mock types bench audit test-etl demo-data register \
        web-install web-types web-lint web-typecheck web-test web-build web-e2e web-dev web-mock

help: ## Lista de objetivos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-18s %s\n", $$1, $$2}'

# ------------------------------------------------------------------ BE-01: entorno, calidad, pruebas
setup: ## Entorno Python 3.12 reproducible desde uv.lock
	$(UV) sync --frozen --all-packages --all-groups

lint: ## Ruff (lint + formato) y mypy estricto
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

format: ## Aplica formato y correcciones automáticas de Ruff
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck: ## mypy estricto sobre apps/api
	$(UV) run mypy

test-unit: ## Pruebas unitarias y de propiedades (sin base de datos)
	$(UV) run pytest apps/api/tests -q

test-contract: ## Contrato: OpenAPI, paridad de enums, Schemathesis (requiere PostgreSQL de pruebas)
	$(UV) run pytest tests/contract -q

test-integration: ## Integración + seguridad + privacidad (requiere PostgreSQL/PostGIS: ver docs/TESTING.md)
	$(UV) run pytest tests/integration tests/privacy -q

test: ## Todo lo que no requiere componentes de otros roles
	$(UV) run pytest -q

test-docker: ## Suite completa dentro de la imagen (incluye PDF/WeasyPrint) contra un PostGIS efímero
	sh infra/scripts/test-docker.sh

test-etl: ## Pruebas de milpa_etl (R1): CLI, catálogos, paquete de demostración
	$(UV) run --all-packages pytest packages/milpa_etl/tests -q

test-science: ## [R2] pruebas científicas T-P/T-G de milpa_core
	@echo "BLOQUEADO: packages/milpa_core (R2) no existe en este repositorio." >&2; exit 1

test-e2e: web-e2e ## Pruebas E2E T-UI/T-A de R4 (Playwright, fixture sintético rotulado)

audit: ## Auditoría de dependencias (pip-audit sobre uv.lock)
	$(UV) export --frozen --all-packages --no-hashes --no-emit-workspace -o /tmp/milpa-requirements.txt
	$(UV) run pip-audit -r /tmp/milpa-requirements.txt --no-deps --disable-pip

# ------------------------------------------------------------------ BE-09: base de datos y despliegue
db-up: ## PostgreSQL 16 + PostGIS (servicio db de Compose)
	docker compose --env-file $(ENV_FILE) up -d --build db

db-down: ## Detiene la base de datos (conserva el volumen)
	docker compose --env-file $(ENV_FILE) stop db

db-migrate: ## Migraciones Alembic (requiere MIGRATION_DATABASE_URL del propietario, ver .env.example)
	cd apps/api && $(UV) run alembic upgrade head

build: ## Construye las imágenes de db y app
	docker compose --env-file $(ENV_FILE) build

up: ## Levanta db + app en modo técnico (sin paquete demo)
	docker compose --env-file $(ENV_FILE) up -d --build

demo: ## Demostración de solo lectura con datos congelados (requiere data/demo de R1)
	@test -f data/demo/EXPECTED.json || { echo "BLOQUEADO: falta data/demo/ (paquete de demostración de R1). R3 no fabrica datasets." >&2; exit 1; }
	DEMO_READONLY=true docker compose --env-file $(ENV_FILE) up -d --build

# ------------------------------------------------------------------ R1: datos (milpa-etl)
ZONE ?= chiquimula_prueba
LAT  ?= 14.8
LON  ?= -89.5
ELEV ?= 790.15

seed: ## [R1] carga catalogs/crops.yaml en ref.* (DATABASE_URL = rol propietario; idempotente)
	$(UV) run milpa-etl seed catalog --catalog catalogs/crops.yaml

data: ## [R1] fetch POWER + curate + validate de una zona (requiere red; ZONE/LAT/LON/ELEV). IMERG: ver packages/milpa_etl/README.md
	$(UV) run milpa-etl fetch power --zone $(ZONE) --lat $(LAT) --lon $(LON)
	$(UV) run milpa-etl curate --zone $(ZONE) --lat $(LAT) --lon $(LON) --elev $(ELEV)
	$(UV) run milpa-etl validate --zone $(ZONE) --lat $(LAT) --elev $(ELEV)

register: ## [R1] registra zona, manifiesto y procedencia en la BD (rol propietario). Ver packages/milpa_etl/README.md
	$(UV) run milpa-etl register manifest
	$(UV) run milpa-etl register zone --zone $(ZONE) --geojson regions/$(ZONE).geojson --region-config regions/pilot_corredor_seco.yaml
	$(UV) run milpa-etl register provenance --zone $(ZONE)

demo-data: ## [R1] regenera data/demo/ (zona SINTÉTICA rotulada + EXPECTED.json); sin red
	DATA_DIR=data $(UV) run milpa-etl build-demo

# ------------------------------------------------------------------ R2: motor científico (NO existe aún)
run-base: ## [R2+R1] corrida base
	@echo "BLOQUEADO: requiere milpa_core (R2); R3 no lo simula." >&2; exit 1

scenarios: ## [R2] grilla de escenarios
	@echo "BLOQUEADO: requiere milpa_core (R2); R3 no lo simula." >&2; exit 1

# ------------------------------------------------------------------ R4: frontend (apps/web)
web-install: ## Dependencias de Node reproducibles (package-lock.json)
	npm ci

web-types: openapi ## Tipos TypeScript desde docs/openapi/openapi.json (los tipos van en apps/web/src/api/types.gen.ts)
	npm run web:types

web-lint: ## ESLint + linter de textos
	npm run lint --workspace @milpa-resiliente/web
	npm run web:test:copy

web-typecheck: ## tsc -b
	npm run typecheck --workspace @milpa-resiliente/web

web-test: ## Vitest (componentes y mock) + linter de textos
	npm run web:test

web-build: ## Construye apps/web/dist (la API lo sirve en / si existe)
	npm run web:build

web-e2e: ## Playwright (PLAYWRIGHT_CHROMIUM_EXECUTABLE si no hay Chromium instalado)
	npm run web:test:e2e

web-dev: ## SPA contra la API real (MILPA_API_PROXY, por defecto http://127.0.0.1:8000)
	npm run web:dev

web-mock: ## SPA con el mock sintético rotulado de R4 (http://localhost:5174)
	npm run web:dev:mock

# ------------------------------------------------------------------ BE-10 / BE-07 / BE-02 / BE-11
reproduce: ## Verifica prerrequisitos y reproduce desde data/demo (falla si faltan R1/R2)
	$(PY) -m api.cli reproduce

report: ## PDF de prueba con la plantilla PROVISIONAL (requiere Pango: usar la imagen Docker)
	$(PY) -m api.cli report-sample --out data/results/sample_report.pdf

openapi: ## Exporta docs/openapi/openapi.json
	$(PY) -m api.cli openapi --out docs/openapi/openapi.json

mock: ## Servidor mock del OpenAPI (solo ejemplos etiquetados) en :4010
	$(UV) run --all-packages uvicorn api.mock.app:app --port 4010

types: web-types ## Alias de web-types

bench: ## Benchmarks T-B (resultados en bench-results/; requiere PostgreSQL de pruebas)
	$(PY) -m api.bench
