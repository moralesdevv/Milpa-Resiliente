# ADR-018: Integración de los entregables de R1 y R4 (`references/`) en el repositorio raíz

- **Fecha:** 2026-11-15 · **Estado:** **propuesto** (afecta contratos compartidos y el árbol de R1/R4)
- **Origen:** instrucción del solicitante: integrar en el backend raíz todo lo actual de `references/` y seguir la especificación; R2 se integrará cuando su responsable lo entregue.

## Decisión
1. **R1 → `packages/milpa_etl`** (workspace uv), con `catalogs/`, `regions/` y `data/curated/` en la raíz (README §23). `references/` queda **intacto**. La API **no importa** `milpa_etl`: lo invoca como proceso (`api.adapters.etl_process.ProcessIngest`, activable con `ETL_INGEST_ENABLED=true`; solo pasos que escriben archivos; el registro en BD es del operador con el rol propietario).
2. **Semillas de R1 como revisión Alembic 0014** (fuentes `POWER_DAILY`, `IMERG_FINAL_V07` —no redistribuible—, `SOIL_CSV_FIXTURE`; catálogo `ref.soil_property`). El script `92_soil_fixture_provenance.sql` **no se aplica** (S-01).
3. **Contrato Parquet ZONAL** (`confirmed_by_delivered_files`): `daily/dekad/coverage` sin `cell_id`, tal como R1 los entrega; `cell_id` queda opcional. El README §13.7 propone clave por celda; la diferencia se **registra**, no se oculta. El directorio curado de una zona es su **nombre** (convención de R1), con respaldo en el UUID.
4. **`data/demo/` + `EXPECTED.json`** = salida de `milpa-etl build-demo` (zona sintética rotulada). `make reproduce` verifica los hashes de archivo y **regenera** el `data_hash` con la ETL en un proceso aparte; sale con código 3 (no éxito) mientras falte R2.
5. **R4 → `apps/web`** (+ `package.json`, `tests/acceptance`, `docs/r4/`, `contracts/openapi.v0.draft.yaml` como histórico, plantillas del informe en `apps/api/templates`). Los tipos TypeScript se generan **desde el OpenAPI de R3** (`docs/openapi/openapi.json`).
6. **OpenAPI publica los DTO de resultado de R2** (README §15: `HeatmapDTO`, `RankResponse`, `StrategyRiskDTO`…) tal como R4 los derivó, marcados `x-contract-status: pending_r2`; R3 no los produce (503 hasta que exista `milpa_core`).
7. **El frontend se adapta a los DTO de R3** (`apps/web/src/api/adapters.ts`): listados `Page[T]`, cargas CSV `text/csv` con 422 por fila, `ScenarioTag[]` con números simples (§15), cifras sin procedencia estructurada rotuladas con procedencia `desconocido` (nunca inventada). El mock de desarrollo de R4 conserva su contrato del borrador y se traduce al formato real en `mock-wire.ts`.
8. **R3 amplía DTO propios** de forma aditiva para lo que la UI necesita y R3 sí conoce: `RunOut` (`label`, `catalog_hash`, `sandbox`, `synthetic_fixture`), `StrategyOut.latest_version`, componentes con nombre de cultivo, `ZoneDetail` (`cells`, `sources`), `DataQualityOut` (`sources`, `comparisons`, `ea_sensitivity_mm_day`, `limitations`), `SoilVoiRequest` opcional, `StabilityRequest.n_samples` opcional.
9. **La imagen** incluye `milpa_etl`, `catalogs/`, `regions/` y copia `data/demo` a `DATA_DIR/demo` si falta (sin red).

10. **`make reproduce` con tolerancia numérica entre plataformas** (rtol 1e-9, atol 1e-12, provisional): el `data_hash` de `build-demo` difiere entre Windows y Linux por ruido de último bit (≤ 4,6·10⁻¹⁶), medido. La tolerancia solo se aplica a columnas de punto flotante; esquema, enteros y texto deben ser idénticos.

## Alternativas descartadas
- Reescribir R1 con Typer/estructura por conectores (README §23): riesgo sin beneficio; se conserva `argparse` verificado (24 autopruebas).
- Que la API importe `milpa_etl`: viola «el backend no importa milpa_etl».
- Ejecutar los SQL de R1 tal cual: rompe la cadena única y evade RLS.
- Inventar procedencia/Indicator para las cifras simples de R3: viola P2/P9.

## Consecuencias / riesgos
- Dependencias nuevas del workspace: `pandas`/`numpy` ya presentes; `requests`; extras opcionales `imerg` (earthaccess, xarray, h5netcdf) y `dem` (rasterio).
- Las cifras simples se muestran con procedencia `desconocido` hasta que R2/R3 acuerden `Indicator` (SPEC-01).
- `register …` y `seed …` requieren credenciales de propietario fuera de la API.
- La ingesta real (red + token NASA) **no se ejecutó**: solo se probó con un ejecutor falso y con los archivos ya curados de R1.

## Pruebas
`packages/milpa_etl/tests`, `apps/api/tests/test_etl_process.py`, `test_reproducibility.py`, `tests/contract/test_r1_artifacts.py`, `tests/integration/test_api_analysis.py` (datos reales de R1), `tests/integration/test_migrations.py`; en `apps/web`: `tsc -b`, ESLint, Vitest y Playwright.

**Aprobadores:** R3, R1, R4; R2 para el punto 6.
