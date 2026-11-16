# ADR-020 — Integración de `milpa_core` (R2) en el repositorio raíz y en la API

**Estado:** propuesto (requiere aprobación humana) · **Fecha:** 2026-11-16

## Decisión
1. **Ubicación:** `packages/milpa_core` (miembro del workspace uv; distribución `milpa-core`, sin dependencias de E/S). `catalogs/r2/` y `regions/r2/` contienen las entradas del motor; los de R1 (`catalogs/crops.yaml`, `regions/pilot_corredor_seco.yaml`) son plantillas `pending` que usa un test de R1 y **no se reemplazan**.
2. **Contrato real de la fachada** (difiere de las firmas del README §10, que no coinciden con el paquete): `run_analysis(ctx, scenario, adaptation, step_days)`, `rank(ctx, run, weights, cfg)`, `rank_stability(base, cfg)`, `soil_voi(ctx, run, base, weights, cfg)`, `make_context`, `run_grid`, `standard_grid`, `build_report(summary, rank, voi, scenarios)`. `api.adapters.milpa_core.DOCUMENTED_FACADE` y `python -m api.cli check-core` verifican estas firmas.
3. **E/S solo en la API:** `api.adapters.core_io` (lectura de YAML y de la serie curada de R1; sin ciencia). El adaptador `MilpaCoreEngine` delega 1:1; los DTO de presentación son los de `milpa_core.dto`.
4. **Persistencia:** `engine.analysis_run` + `engine.scenario_run` + Parquet con SHA-256 bajo `DATA_DIR/results/…`, escritos por los trabajos (`jobs/handlers/engine_jobs.py`). `python -m api.cli register-engine` (rol propietario) registra `ref.catalog_release` y las 45 `engine.scenario_def`.
5. **Identificación de estrategias:** el motor las identifica por código (`E1_REF_MAIZ`…); los parámetros `strategy`/`variety` de `heatmap` y `dekad-chart` pasan de UUID a código (`^[A-Za-z0-9_.-]{1,64}$`).
6. **Reproducibilidad:** `data/demo/EXPECTED_ENGINE.json` (huella de la corrida base sobre la serie sintética rotulada, resultados redondeados a 6 decimales) y `make reproduce` la recalcula y compara.
7. **Paridad de enums** R2 ↔ PostgreSQL verificada por `tests/contract/test_enum_parity.py`.

## Pendiente
Las decisiones marcadas **[Propuesto R2]** en `docs/r2/METHODS.md` siguen sin aprobar; todo opera en modo `sandbox` con evidencia C. `mypy --strict` sobre `milpa_core`: 183 errores de tipado por corregir (sin cambiar la ciencia).
