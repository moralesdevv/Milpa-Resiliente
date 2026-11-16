# Estado de integración (R3 ↔ R1 / R2 / R4)

> **Actualización 2026-11-16:** R2 ya NO está pendiente. Estado: `milpa_core` integrado (ADR-020); `make reproduce` completo (datos R1 + corrida base R2 sobre la serie sintética rotulada); endpoints de resultados devuelven DTO reales. Siguen pendientes: corridas con parcela/suelo, PDF fuera de Docker, fuentes no integradas (ver `docs/DATA_SOURCES.md` y la tabla de estado en My zone).

Actualizado: 2026-11-15 (integración de `references/` en la raíz, ADR-018). Estados permitidos: `pending` · `contract_defined` · `adapter_ready` · `waiting_for_dependency` · `integrated` · `verified`.
`integrated` = el adaptador pasa pruebas **contra el componente real** (no contra dobles). `verified` = además existe una prueba de aceptación reproducible en CI. **Ninguna interfaz está `verified`**: GitHub Actions no se ha ejecutado, y la ingesta real (red + token NASA) ni la integración con R2 se han ejercido.

| # | Interfaz | Dueño | Estado | Qué existe | Evidencia (ejecutada) | Qué falta |
|---|---|---|---|---|---|---|
| 1 | `coverage.parquet` → `GET /zones/{id}/data-quality` | R1 | **`integrated`** | Contrato zonal `confirmed_by_delivered_files`; nombre de zona = directorio curado | `test_api_analysis.py::…real_r1…`; verificación manual: cargador de R1 → BD → API con datos reales (200 filas, fuentes, comparaciones) | R1/R2: confirmar si se añade `cell_id` (README §13.7) |
| 2 | `daily.parquet`, `dekad.parquet` | R1 | `integrated` (lectura) | Lectura con verificación de hash; ningún endpoint los sirve (los consume el motor) | `test_r1_artifacts.py::…zonal_contract…` (9 131 y 900 filas) | Ensamblado de `ClimateSeries` (R2) |
| 3 | `data/demo/` + `EXPECTED.json` | R1 | **`integrated`** | Paquete sintético rotulado generado con `milpa-etl build-demo`; `make reproduce` verifica hashes y regenera el `data_hash` | `test_reproducibility.py` (4 pruebas nuevas); `make reproduce` → 5 `VERIFICADO`, exit 3 | Recomputación de cifras (R2) |
| 3b | Manifiesto de ingestas (`data/manifest/ingestions.jsonl`) | R1 | `waiting_for_dependency` | `register manifest` portado | — (R1 no entregó el manifiesto ni los JSON crudos) | Se genera al descargar (red + token) |
| 4 | Disparo de ingesta (`zone_ingest`) | R1 | `adapter_ready` | `ProcessIngest` (proceso, sin importar `milpa_etl`), `ETL_INGEST_ENABLED` | `test_etl_process.py` (ejecutor **falso**) | Primera ingesta real con red y token |
| 5 | CSV de suelo v1 (README §9) | R1 | **`integrated`** (validación) | `SOIL_CSV_V1` acepta los 7 registros válidos de R1 y rechaza los 9 inválidos | `test_r1_artifacts.py` | Guardar mediciones exige reglas de evidencia de R2 (503) |
| 6 | Catálogos `ref.*` | R1 | **`integrated`** | Migración 0014 (fuentes, `soil_property`); `milpa-etl seed catalog` portado a psycopg 3 | `test_migrations.py`; ejecución real de `seed catalog` (2 cultivos, idempotente) | Variedades, Kc, umbrales: `pending` en R1 (P9) |
| 7 | DDL `prov/ref/geo/soil/econ` | R1/R3 | `integrated` (cadena única) | 14 revisiones; `register zone` de R1 corre sobre el esquema de R3 | `test_r3_schema_covers…`, ejecución real de `register zone` | Aprobación del ADR-003 |
| 8 | Fachada `milpa_core` (5 funciones) | R2 | `adapter_ready` | `check_core_contract`, `MilpaCoreEngine` (`PENDING_R2`) | `test_adapters_and_static.py` (módulo de prueba) | Paquete de R2 |
| 9 | DTO de resultado (`HeatmapDTO`, `RankResponse`, `StrategyRiskDTO`, …) | R2 | `contract_defined` | Publicados en el OpenAPI como `pending_r2` (forma derivada por R4 del §15); R3 los transporta opacos y responde 503 | `test_openapi_contract.py`, `tsc -b` de R4 con 0 errores | Los DTO reales de R2 |
| 10 | Enums `milpa_core.enums` | R2 | `contract_defined` | Espejo provisional + paridad Python↔SQL↔OpenAPI↔R4 | `test_enum_parity.py`, `test_r4_artifacts.py` | Import real |
| 11 | Reglas de evidencia A/B/C | R2 | `waiting_for_dependency` | `EvidencePort` | `test_csv_persist_*` (doble) | Implementación de R2 |
| 12 | Errores tipados del motor | R2 | `adapter_ready` | `translate_engine_error` | `test_adapters_and_static.py` | Nombres reales |
| 13 | `ReportModel`/`build_report` | R2 | `waiting_for_dependency` | `ReportInput` provisional | `test_reports.py` | `ReportModel` y adaptador |
| 14 | Plantilla del informe | R4 | **`integrated`** (render) | Plantillas de R4 en `apps/api/templates`; `render_template_pack` con CSS incrustado; PDF A4 real | `test_r4_artifacts.py` (28 en Docker) | Contexto desde `report_model` (R2) |
| 15 | Consumo del OpenAPI | R4 | **`integrated`** | `apps/web` en la raíz; tipos generados desde el OpenAPI de R3; adaptadores de formato | `tsc -b` 0 errores · ESLint limpio · Vitest 26/26 · linter de textos 8/8 · **Playwright 27 aprobadas, 3 `fixme` de R4** (contra el mock sintético) | Playwright **contra la API real**: no ejecutado |
| 16 | Tipos TypeScript | R4 | `integrated` | `npm run web:types` (usa `docs/openapi/openapi.json`) | ídem | CI de GitHub sin ejecutar |
| 17 | Estáticos del frontend | R4 | `integrated` | `vite build` → `apps/web/dist` (la API lo sirve en `/`) | build ejecutado | Etapa de build en la imagen Docker |
| 18 | Reproducción (`make reproduce`) | R1+R2 | `waiting_for_dependency` (parcial) | Capa de datos verificada y regenerada; sin R2 sale con código 3 | `test_reproducibility.py` | Motor de R2 |

## Cómo promover un estado
1. `adapter_ready → integrated`: el componente real está presente y el adaptador pasa pruebas **contra él**.
2. `integrated → verified`: prueba de aceptación reproducible en CI.
3. Registrar el cambio aquí y, si cambia un contrato, en un ADR.

## Advertencias vigentes (ver `docs/HANDOFF.md`)
- La imagen `runtime` de Docker **no se reconstruyó ni se probó con `docker compose up`** después de integrar R1/R4 (solo la etapa `test`).
- `ProcessIngest` con `ETL_INGEST_ENABLED=true` (incluida su consulta de zona) **no tiene prueba de extremo a extremo**; solo ejecutor falso.
- Playwright corrió contra el mock sintético, **no contra la API real**.
- Los ADR 003, 007, 009, 010, 015, 016, 017 y 018 están **propuestos, no aprobados**.
- R2 no existe: nada científico se calcula.
