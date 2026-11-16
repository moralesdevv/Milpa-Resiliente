# Contrato de datos R1 → R3

> **Actualizado tras recibir `references/Milpa-Resiliente-R1` (auditoría 2026-11-15).** R1 ya entregó archivos reales y R3 los probó (ver `docs/auditoria/matriz_compatibilidad.md`). Resumen: el CSV de suelo **es compatible**; el Parquet se lee con un **contrato zonal** (sin `cell_id`, tal como R1 lo entrega; ADR-018); sus semillas son la revisión Alembic 0014; el script 92 **no se aplica** (elimina `security_invoker`, S-01; el servicio no arranca si se ejecuta). R1 vive ahora en `packages/milpa_etl` (ver su README).

R3 **consume** datos curados; no descarga, limpia ni cura (spec R3 §2.3). Todo lo marcado «propuesto» proviene del README integral y **no es operativo hasta que R1 lo confirme**. R3 no infiere columnas ni fabrica archivos.

## 1. Ubicación (bajo `DATA_DIR`)
| Ruta | Clave | Uso en R3 |
|---|---|---|
| `curated/<zona>/coverage.parquet` | `(cell_id, variable, year)` | `GET /v1/zones/{id}/data-quality` (**implementado**) |
| `curated/<zona>/daily.parquet` | `(cell_id, obs_date)` | lo consume el motor (R2); R3 solo valida existencia/hash |
| `curated/<zona>/dekad.parquet` | `(cell_id, year, dekad)` | ídem |
| `results/<run_id>/<scenario_id>/<adaptation>/{cycle,cohort}_result.parquet` | ver README §13.7 | escritos/leídos con `ObjectStore` sin sobrescritura |
| `manifest/`, `demo/EXPECTED.json` | — | verificación de hashes (`make reproduce`) |

`<zona>` es el `zone_id` (UUID) o el código que R1 defina; R3 solo admite `[A-Za-z0-9_+-]{1,64}` (sin `/`, `..`).

## 2. Columnas que R3 exige hoy (`api.storage.parquet`, estado `confirmed_by_delivered_files`)
- `coverage`: `variable, year, n_expected, n_valid, pct_missing` (`cell_id` opcional).
- `daily`: `obs_date, precip_mm, et0_mm, qc_flags`. `dekad`: `year, dekad, p_mm, et0_mm, n_days, n_valid_days`.
- Directorio: `curated/<nombre de zona>/` (convención de R1; respaldo `curated/<zone_id>/`).
El resto de columnas (`tmax_c … qc_flags`, `pef_mm_<método>`) se transporta sin interpretarse. **Si faltan columnas exigidas → 503 `DATASET_INCOMPATIBLE`; si no existe el archivo → 503 `DATASET_UNAVAILABLE`.** Nulos: se devuelven como `null`, nunca como 0.

## 3. Lo que R1 debe confirmar/entregar (checklist)
1. Convención de nombres/rutas y valor de `<zona>`.
2. Esquema completo (columnas, tipos, unidades en el nombre, nulos, `qc_flags` como bits).
3. Versión del dataset y **SHA-256 esperado** + algoritmo del *hash lógico* del Parquet.
4. Formato del manifiesto de ingestas (`prov.ingestion_run`, `raw_sha256`) y de `data/demo/EXPECTED.json`.
5. Compatibilidad hacia atrás y política de archivos faltantes/corruptos.
6. **Mecanismo de disparo de la ingesta** desde la API sin importar `milpa_etl` (¿CLI/subproceso, cola de manifiestos?) y su idempotencia (hoy `zone_ingest` NO se reencola tras un reinicio).
7. ~~Esquema CSV de suelo v1~~ **Resuelto**: lo fija el README §9 y R1 lo cumple (`suelo.csv`). R3 lo implementa como `SOIL_CSV_V1` (ADR-017). Pendiente de R1: plantilla `docs/templates/soil.csv`.
8. Propiedad y aprobación del DDL de `prov/ref/geo/soil/econ` (ADR-003); carga de catálogos con citas.
9. `data/demo/` redistribuible, **sin datos personales ni coordenadas de parcelas** (la prueba `test_demo_package_has_no_personal_data_or_exact_coordinates` lo escaneará).

## 4. Qué entrega R3 a R1
Infraestructura (`docker compose`, Alembic único, `ObjectStore`), lector Parquet con verificación de hash, secretos solo por entorno (`EARTHDATA_TOKEN` se define pero la API no lo usa).

## 5. Pruebas de aceptación sugeridas al integrar
Reemplazar los archivos sintéticos de `test_api_analysis.py` por un fixture real de R1; verificar `expected_sha256` contra el manifiesto; ejecutar `tests/privacy` sobre `data/demo/`.

## 6. Estado medido frente a los archivos reales de R1 (2026-11-15)
| Artefacto | Resultado con R3 | Prueba |
|---|---|---|
| `suelo.csv`, `suelo_prueba.csv` (7 filas) | Aceptadas | `tests/contract/test_r1_artifacts.py` |
| `suelo_invalido_p014.csv` (9 filas, 9 defectos) | Rechazadas, cada una con su error (`out_of_range`, `method_not_accepted`, `texture_sum`, `future_date`, `depth_order`, `not_numeric`, `out_of_range`, `invalid_value`, `formula_injection`) | ídem |
| `daily/dekad/coverage.parquet` | Leídos con el contrato zonal (9 131 · 900 · 200 filas); sin `cell_id` ni `tmean_c`; `obs_date` `timestamp` (diferencias con README §13.7 registradas, ADR-018) | `test_r1_parquet_satisfies_the_zonal_contract_r3_reads` |
| `sql/*.sql` | 47 tablas de R1 ⊂ 48 de R3; en orden corregido (`04_geo` antes de `03_ref`) coinciden salvo 4 puntos | `test_r3_schema_covers_everything_in_the_r1_ddl` |
| `sql/90, 91, 93` | Cargan sin error | `test_r1_seed_scripts_load_into_the_r3_schema` |
| `sql/92` | **Evade RLS** (fuga demostrada) | `xfail(strict)` + `test_r1_script_92_is_detected_by_the_startup_guard` |
