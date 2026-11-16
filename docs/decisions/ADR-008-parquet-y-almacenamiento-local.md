# ADR-008: Parquet y adaptador de almacenamiento local

- **Fecha:** 2026-11-14 · **Estado:** aceptado (patrón); contratos de columnas **pendientes de confirmación de R1**

## Contexto
Series y matrices viven en Parquet bajo `DATA_DIR` (`curated/<zona>/{daily,dekad,coverage}.parquet`, `results/<run_id>/<scenario_id>/<adaptation>/…`). R1 produce, R2 define resultados, R3 lee/valida.

## Decisión
- `ObjectStore` (Protocol) con implementación `LocalObjectStore`: rutas relativas validadas segmento a segmento (sin `..`, absolutas, vacías ni caracteres raros), `resolve()` comprueba que el destino final (tras symlinks) siga bajo la raíz; escritura atómica; **no sobrescribe** resultados salvo `overwrite=True` explícito.
- `ParquetDatasetReader`: verifica existencia, tamaño máximo, SHA-256 esperado (si se conoce), legibilidad y columnas del `ParquetContract`. **No infiere columnas**: solo exige las que el README §13.7 propone, con `status="proposed_pending_r1_confirmation"`. Errores tipados → 503 `DATASET_UNAVAILABLE` / `DATASET_INCOMPATIBLE`; las rutas internas no salen en los mensajes.
- `write_parquet_deterministic`: orden fijo de filas/columnas, sin estadísticas, compresión fija, sin sobrescritura (README §25).

## Alternativas
S3/MinIO (descartado en el MVP), base de datos para las series (descartado por volumen).

## Consecuencias / riesgos
Cuando R1 confirme esquemas y manifiesto se sustituye el estado del contrato y se añaden las columnas confirmadas. Riesgo: lectura completa en memoria de archivos grandes (límite configurable; benchmarks BE-11).

**Aprobadores:** R1 (contrato), R3.
