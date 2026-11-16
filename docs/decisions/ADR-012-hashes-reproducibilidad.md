# ADR-012: Hashes, linaje y reproducibilidad

- **Fecha:** 2026-11-14 · **Estado:** aceptado (mecanismos); `make reproduce` completo **bloqueado por R1/R2**

## Decisión
- SHA-256 (`hashlib`). Hash de configuración/parámetros = SHA-256 de **JSON canónico** (claves ordenadas, UTF-8, sin NaN). Hash lógico de tabla: columnas ordenadas, filas por claves, nulos como `null` (nunca 0). `data_hash` = hash de `{raw_sha256 ordenados, hash lógico del curado}` (README §25).
- `RunIdentifiers` (`code_version, region_config_hash, catalog_hash, data_hash, params_hash, seed`) valida formato y detecta cambios (`diff`).
- Resultados en `results/<run_id>/<scenario_id>/<adaptation>/` sin sobrescritura; Parquet determinista.
- Manifiesto de verificación de archivos (`build_manifest/verify_manifest`) **provisional** (`r3-manifest-v0-provisional`) hasta que R1 defina el oficial. Una entrada ausente produce `MissingInputError` con el nombre exacto; no se calculan hashes de datos inexistentes.
- `make reproduce` → `api.cli reproduce`: comprueba `milpa_core` y `data/demo/EXPECTED.json`; sale con 2 (faltan entradas) o 3 (entradas presentes pero comparación pendiente de contrato). **Nunca simula éxito.**
- Igualdad por hash solo dentro de la misma imagen de contenedor; tolerancia numérica entre plataformas se fija por ADR cuando R2 lo defina.

## Consecuencias / riesgos
(+) Trazabilidad de entradas. (−) La reproducción científica no está demostrada hasta integrar R1+R2. **Aprobadores:** R1, R2, R3.
