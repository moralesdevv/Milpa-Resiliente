# Matriz de compatibilidad (FASE 4)

> **Actualización posterior (ADR-018):** R1 y R4 se integraron en la raíz del repositorio (`packages/milpa_etl`, `apps/web`, `catalogs/`, `regions/`, `data/`). El contrato Parquet zonal de R1 es ahora el que lee R3 (C-02 resuelto en R3; la diferencia con el README §13.7 queda registrada). Las cifras de este documento corresponden a la auditoría previa a esa integración salvo donde se indique.

Cada fila es una comparación **ejecutada** entre dos artefactos reales (no una impresión). Clasificación del encargo: *Implementado correctamente · Implementado parcialmente · Incompatible · No implementado · Pendiente de validación científica · No aplicable*. «Resuelto» = corregido en R3 en esta auditoría; «Abierto» = requiere decisión del equipo indicado. Reproducir con los comandos de `informe_validacion.md`.

## A. R1 (datos) ↔ especificación ↔ R3

| ID | Elemento | Comparación | Clasificación | Estado / decisión |
|---|---|---|---|---|
| **S-01** | `sql/92_soil_fixture_provenance.sql` de R1 sobre la base de R3 | `CREATE OR REPLACE VIEW soil.property_status` sin `WITH (security_invoker = true)` ⇒ `reloptions` pasa de `{security_invoker=true}` a `NULL`. Con 2 parcelas ajenas y un usuario sin relación: **16 filas visibles** (RLS en `farm.parcel` da 0); con la opción restaurada, 0. Sin `FORCE RLS` y con el propietario como dueño de la vista, el rol de la app consulta como propietario | **Incompatible (seguridad)** | R3: **Resuelto en defensa** (el servicio no arranca si ocurre; ADR-017). R1: **Abierto** (corregir el script). `xfail(strict)` en `test_r1_script_92_keeps_the_view_under_rls` |
| C-01 | `sql/` de R1 | Aplicados en orden de nombre, `03_ref.sql` falla (`geo.region` no existe aún; FK hacia adelante) — el mismo problema que ADR-003 resolvió en R3 | Incompatible | Abierto (R1). R3 ya tiene una cadena Alembic única que lo resuelve |
| C-02 | `daily/dekad/coverage.parquet` | Spec §13.7: clave `(cell_id, …)`, columna `tmean_c`, `obs_date` fecha. R1: **sin `cell_id`** (serie ponderada por zona), sin `tmean_c`, `obs_date` `timestamp[us]`, + `precip_power_mm`, `precip_imerg_mm`, 4×`pef_mm_*`, `pef_month_total_usda_scs_fao`. El lector de R3 responde `503 DATASET_INCOMPATIBLE` (tipado, sin 500) | **Incompatible** con el README §13.7 | **R3 adoptó el contrato zonal** (`confirmed_by_delivered_files`, ADR-018) y lee los archivos reales de R1. **Abierto** (R1+R2): ¿se mantiene la serie por zona o se añade `cell_id`? La serie por zona pierde la información de las 12 celdas IMERG |
| C-07 | `ip_id` en `econ.price_record` y `soil.estimate` | R1 `NOT NULL`; README §13.4 nullable. R3 sigue el README | Implementado parcialmente (R1 más estricto) | Abierto: confirmar. Prueba fija la excepción |
| C-08 | Vista `soil.property_status` | R1 (92) añade rama «procedencia `desconocido` ⇒ `desconocido`»; el README no la define | Pendiente de validación | Abierto (R1/R2) |
| C-12 | ET0 y Pef calculados en R1 | README §11.3-11.4 los asigna a `milpa_core` (R2). Las fórmulas de R1 coinciden con el texto y pasan 24/24 autopruebas; R1 las rotula «respaldo local; confirmar con R2» | Implementado parcialmente (duplicación de ciencia) | Abierto (R1/R2): una sola implementación. **R3 no recalcula ni lo uno ni lo otro** |
| C-13 | `ingestar_suelo_db.py` | Escribe con el rol propietario (sin RLS ni consentimiento), evidencia fija `C`, `evidence_rule_id='soil_fixture_c'` inexistente en `evidence_rules.yaml`; solo fixtures sintéticos | Incompatible con el flujo de R3 (que no asigna evidencia: ADR-009) | Abierto (R1/R2) |
| C-16 | `data_hash` | R1: SHA-256 de la lista de `raw_sha256` + hash lógico (`curated_meta.json`); R3: hash canónico de datos y manifiesto propio (`r3-manifest-v0`) | Pendiente de validación | Abierto: pruebas cruzadas cuando exista `EXPECTED.json` |
| — | CSV de suelo (4 archivos) | Tras C-15, R3 acepta 7 filas válidas y rechaza las 9 inválidas de R1 con el error esperado por fila | Implementado correctamente | Resuelto |
| — | DDL (tablas, columnas, restricciones, enums) | Catálogo normalizado de 603 (R1) vs 637 (R3) líneas: todo lo de R1 está en R3 salvo C-07, `engine.job.kind` (+2 tipos) y el nombre de un índice; R3 solo añade | Implementado correctamente | Resuelto (prueba `test_r3_schema_covers_everything_in_the_r1_ddl`) |
| — | Semillas 90/91/93 de R1 | Se cargan sobre el esquema de R3 sin error (2 fuentes, 8 propiedades de suelo) | Implementado correctamente | Resuelto |
| — | Autopruebas de R1 | 24/24 OK | — | — |

## B. R4 (frontend) ↔ especificación ↔ R3

| ID | Elemento | Comparación | Clasificación | Estado / decisión |
|---|---|---|---|---|
| C-06 | Salud | R4 `GET /v1/healthz`; especificación y R3 `GET /healthz` | Incompatible (R4 se aparta de la especificación) | Abierto (R4) |
| C-10 | Plantillas de ruta | R3 usaba `{zone_id}`…; especificación y R4 `{id}`, `{v}`, `{property}`. `openapi-fetch` indexa por plantilla literal | Incompatible (R3) | **Resuelto** (alias de `Path`): 358 → 302 errores TS |
| C-09 | Login | R4 `Session{access_token, expires_in, role}`; R3 `TokenResponse{access_token, token_type, expires_at}`. Ninguna especificación lo define | Incompatible | **Resuelto** (R3 añade `expires_in` y `role`, aditivo) |
| C-03 | Cancelar trabajo | R4 `204`; R3 `200` + `JobOut` | Incompatible | Abierto (R3+R4); la especificación no fija el código |
| C-04 | Listados | R4 arreglos en `/zones`, `/catalog/crops`, `/catalog/references`; spec R3 línea 489 `Page[T]` | Incompatible (R4) | Abierto (R4 adapta o RFC) |
| C-05 | Carga de CSV | R4 `200 {accepted, errors[{row,column,message}]}`; R3 `200` con conteos o `422 problem+json` `errors[{loc,msg,code}]` | Incompatible | Abierto (R3+R4) |
| C-11 | `Indicator` en toda cifra (SPEC-01 de R4) | Decisión local de R4 que cambia DTO del §15 (p. ej. `ScenarioTag`, cobertura, pesos) | Pendiente de validación | Abierto (R2/R3): R3 no la adopta sin contrato |
| C-17 | ~40 DTO de presentación (`HeatmapDTO`, `RankResponse`, `StrategyRiskDTO`, `IndicatorNumber`…) | En R3 son `*Payload` opacos `pending_r2`; R4 los importa por nombre | No implementado (depende de R2) | Abierto (R2) |
| C-18 | `RunDTO`, `ParcelDTO`, `DataQualityDTO`, `ScenariosOut`, `SoilCsvResult` | Diferencias de forma en endpoints de R3 (ver `auditoria_R4.md` §2) | Implementado parcialmente | Abierto (R3+R4) |
| — | `SoilPropertyStatusDTO` | 9 de 9 campos idénticos | Implementado correctamente | — |
| — | `ProvenanceInfo` (§15) | Nombres de R4 y de la especificación; R3 los adopta (+`ip_id`, `indicator_code`, `unit`) | Implementado correctamente | **Resuelto** |
| — | Enums | 14/14 iguales al espejo de la especificación; 3 compartidos en OpenAPI idénticos | Implementado correctamente | — |
| — | `Problem` / `ProblemDetail` | Mismos 8 campos; R3 emite todos los que R4 exige | Implementado correctamente | — |
| C-14 | Plantilla de informe | Renderiza en el sandbox de R3; PDF A4 de 2 páginas en WeasyPrint 70; contexto `labels/mode/strategies/ranking/annex` debe construirse desde `report_model` (R2, inexistente). Sin R3, el CSS enlazado se perdía en silencio | Implementado parcialmente | R3: **Resuelto** el CSS. Abierto (R2): `report_model` y adaptador |
| — | Cliente TS | `tsc -b`: 0 errores contra el borrador de R4; 302 contra el OpenAPI de R3 | Implementado parcialmente | Mejorará al llegar los DTO de R2 |

## C. R3 ↔ especificación (desvíos propios hallados)

| ID | Elemento | Desvío | Clasificación | Estado |
|---|---|---|---|---|
| C-15 | Contrato del CSV de suelo | R3 inventó `SOIL_CSV_V0_PROVISIONAL` existiendo uno en el README §9 | Incompatible | **Resuelto** (`SOIL_CSV_V1`) |
| — | Defensa de RLS | No había comprobación al arrancar | No implementado | **Resuelto** (`api.db.invariants`) |

## D. Cuestiones científicas que requieren decisión (no las toma R3)

| ID | Qué | Por qué existe el conflicto | Propuesta (no aplicada) | Decide |
|---|---|---|---|---|
| SV-01 | Lluvia: 81 % de los días de POWER y 19 % de IMERG (2021-01 a 2025-09) en una misma serie de 25 años, sin corrección de sesgo | README §21: IMERG B / POWER solo contraste; R1 la usa como primaria en 2001-2020 y deja la regla «pendiente de R2». R1 mide (en `precip_validation.json`) correlación diaria 0,124 y cociente de totales IMERG/POWER 0,813 (2021: 0,524; 2024: 1,003); su `validation_report.json`, de otra corrida, da 0,144 | Documentar como limitación en todo informe; evaluar corrección (bit 8) con estación local; reportar sensibilidad por periodo | R2 + asesor (DP-04/05/09) |
| SV-02 | Sin Kc, fenología, ventanas críticas, umbrales, variedades, calendario, zona | P9: sin cita ⇒ `pending` | No hay nada que inventar: obtener las fichas ICTA/MAGA y citas | R1 + asesor (DP-01…05, 12) |
| SV-03 | `fallback_share_pct` = 0,0 vs `fallback_share_pct_full_series` = 81,01 | La regla de degradación a C no dice cuál aplica | Definir cuál alimenta `fallback_share_max` | R1/R2 |
| SV-04 | ET0 negativo sin acotar no se marca | §11.3 pide bandera | Añadir bandera en la salida | R1/R2 |
| SV-06 | `precip_validation.json` y `validation_report.json` (R1) dan estadísticos distintos para IMERG vs POWER (corr. diaria 0,124 con 1 734 días vs 0,144 con 1 369) | Dos corridas de la validación en momentos distintos; no se indica cuál vigente | R3 transporta `precip_validation.json` (el declarado en el README de R1); R1 debe regenerar o retirar el otro | R1 |
| SV-05 | Día UTC vs UTC−6 en POWER/IMERG | README §9 lo declara limitación `[Verificar]` | Mantener la limitación; la agregación por decena la mitiga | R1 |
| SV-06 | Pef por fórmulas mensuales aplicadas a decenas (desagregación proporcional) | README §11.4 lo declara «asignación, no proceso físico»; `peff_sensible_al_metodo` | Sin cambio: ya está declarado | R2 |

## E. Principios científicos del encargo (§6): ¿los respeta lo que existe?

| Principio | Estado |
|---|---|
| Distinguir asociación de rotación; fecha/variedad ≠ rotación | El DDL (`strategy_axis_t`, `changes_from_reference`) y el DTO lo exigen; **la lógica es de R2 (no existe)** |
| No inventar calendarios, variedades, rendimientos, parámetros | R1 lo cumple (todo `pending`); R3 y R4 no introducen ninguno |
| Distinguir observación, estimación, supuesto | `provenance_t` (`medido/satelital/estimado/modelado/declarado/desconocido`); R3 lo transporta sin reinterpretar |
| Precipitación − ETc no es déficit real de la raíz | Etiqueta `indicador_exposicion_climatica` (R2); R4 muestra la advertencia |
| Los satélites no miden la salud del suelo | R3/R4 no lo afirman; `soil.estimate` es siempre `estimado` |
| Faltante no se transforma en cero | R1 (lluvia nunca interpolada; `NaN`), R3 (`null`; CSV vacío = sin fila) — verificado |
| Registrar fuente, fecha, resolución, método | `prov.indicator_provenance`; R1 lo escribe, R3 lo expone (`ProvenanceInfo`) |
| Incertidumbre y reproducibilidad | `curated_meta`, hashes; equivalencia entre R1 y R3 sin verificar (C-16) |
