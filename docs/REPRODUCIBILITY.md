# Reproducibilidad y linaje (BE-10)

## Identificadores de una corrida (README §25)
`code_version` (SHA Git + versión del motor) · `region_config_hash` · `catalog_hash` · `data_hash` · `params_hash` · `seed`. Se guardan en `engine.analysis_run`; la API los **transporta** (`GET /v1/runs/{id}`) y los valida (`RunIdentifiers`: SHA-256 en minúsculas, `seed` entero ≥ 0). `diff()` identifica cuáles cambiaron entre dos corridas. R3 no calcula hashes de entradas ausentes.

## Hashes (`api.reproducibility.hashing`)
- `sha256_file` / `sha256_bytes`.
- `canonical_hash(obj)`: JSON canónico (claves ordenadas, sin espacios, UTF-8, sin NaN) → `params_hash`, `region_config_hash` de configuraciones normalizadas.
- `logical_dataframe_hash(df, sort_keys)`: independiente del orden físico de filas/columnas; nulos como `null` (≠ 0). Probado con Hypothesis.
- `data_hash(raw_sha256s, curated_logical_hash)`: SHA-256 de la lista **ordenada** de hashes crudos + hash lógico del curado.

## Resultados sin colisiones
`results/<run_id>/<scenario_id>/<adaptation>/…` con `LocalObjectStore` (no sobrescribe; `StorageObjectExists`). `write_parquet_deterministic` fija orden de filas/columnas, compresión y sin estadísticas ⇒ mismo contenido lógico ⇒ mismo archivo.

## Manifiesto y verificación
`build_manifest` / `verify_manifest` (formato **provisional** `r3-manifest-v0-provisional` hasta que R1 defina el oficial): rutas ordenadas, `sha256`, `size`; informa archivos **faltantes**, **con hash distinto** y rutas fuera de la base. CLI: `python -m api.cli verify-manifest <manifest> --base <dir>`; `python -m api.cli hash <archivo>`.

## `make reproduce`
Ejecuta `python -m api.cli reproduce` y **nunca simula éxito**:
| Código | Significado |
|---|---|
| 2 | Faltan entradas: lista exacta (`packages/milpa_core` (R2), `data/demo/` (R1), `data/demo/EXPECTED.json` (R1)) |
| 3 | Entradas presentes pero la comparación de hashes no está contratada (formato de `EXPECTED.json`, `run_analysis`): `waiting_for_dependency` |
| 0 | Reservado para cuando R1+R2 entreguen y se implemente la comparación |
**Estado actual: código 2.** La reproducción científica **no** está demostrada.

## Niveles de garantía (README §25)
Mismo hash dentro de la misma imagen de contenedor; entre plataformas, tolerancia numérica fijada por ADR (pendiente de R2). Dependencias fijadas en `uv.lock` (CI instala con `--frozen`); imagen con versiones fijadas (uv 0.13.8, `postgis:16-3.4`, `python:3.12-slim-bookworm`).

## Documentación pendiente de otros roles
`METHODS.md`, `DATA_SOURCES.md`, `REPRODUCE.md`, `ADD_A_REGION.md` (R1/R2).
