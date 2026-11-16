# Matriz de trazabilidad (FASE 4)

Relaciona cada regla (ver `reglas_consolidadas.md`, IDs `RC-*`) con su fuente, el paquete que la implementa, el módulo del backend, la implementación y la prueba. **No se marca «implementado» por la mera existencia de un archivo**: la columna *Evidencia* indica si la prueba se **ejecutó** (E) en esta auditoría, es **declarada** por su autor sin re-ejecutar (D), o **no existe** (—).

El encargo pedía la columna «Estrategia»: R1/R3/R4 no son estrategias (ver `inventario_documental.md` §0); se usa «Paquete». Ninguna regla agronómica de estrategia tiene implementación porque **no existe R2** ni parámetros con cita.

Rutas de módulos relativas a `apps/api/src/api/`. Pruebas relativas a la raíz. «R1:» = `references/Milpa-Resiliente-R1/`.

| Regla | Fuente | Paquete | Módulo backend | Implementación | Prueba (evidencia) | Clasificación |
|---|---|---|---|---|---|---|
| RC-B1 API `/v1`, `problem+json`, `/healthz` | README §16; R3 §536 | R3 | `main.py`, `errors.py`, `routers/*` | 34 operaciones; errores 8 campos | `tests/contract/test_openapi_contract.py`, `test_schemathesis.py` (E) | Implementado correctamente |
| RC-B2 Plantillas `{id}`/`{v}`/`{property}` | README §16 | R3 | `routers/_common.py` (alias `Path`) | Nombres de la especificación en OpenAPI | `tests/contract/test_r4_artifacts.py::test_routes_match…` (E) | Implementado correctamente (corregido) |
| RC-B3 `Page[T]` por cursor | R3 l.489 | R3 | `pagination.py` | cursor opaco, tope configurable | `tests/integration/test_api_analysis.py` (E) | Implementado correctamente |
| RC-B4 Trabajos (202, idempotencia, huérfanos) | README l.1572; R3 §715-742 | R3 | `jobs/*`, `services/jobs.py` | `ProcessPoolExecutor`, reclamo atómico, recuperación | `tests/integration/test_jobs.py` (E) | Implementado correctamente |
| RC-B5 JWT, Argon2id, RBAC, RLS, consentimiento | R3-F02…F05 | R3 | `security/*`, `services/access.py`, migración 0012 | RLS con rol sin BYPASSRLS; bloqueo progresivo | `test_rls.py`, `test_api_auth.py` (E) | Implementado correctamente |
| RC-B5b RLS no evadible por SQL ajeno | S-01 | R3 | `db/invariants.py`, `main.py` | El servicio no arranca si falla | `test_service_refuses_to_start…`, `test_r1_artifacts.py` (E) | Implementado correctamente |
| RC-B6 Privacidad (rejilla ≥ 1 km, sin coords en logs/PDF) | R3 §9; README §22 | R3 | `security/privacy.py`, `logging_config.py` | Generalización en servidor; redacción de logs | `tests/privacy/*` (E) | Implementado correctamente |
| RC-B7 PDF sin recursos externos, hash | README §22 | R3+R4 | `reports/*` | WeasyPrint 70 `URLFetcher` `data:`; CSS local incrustado | `apps/api/tests/test_reports.py`, `test_r4_artifacts.py::…a4…` (E en Docker) | Implementado parcialmente (falta `report_model`) |
| RC-B8 Docker de 2 servicios | R3 BE-09 | R3 | `docker-compose.yml`, `infra/` | `db` + `app`, uid 10001 | `test_boundaries.py` (E); `docker compose up` real (E, sesión previa) | Implementado correctamente |
| RC-S1 CSV de suelo con las columnas del README | README §9 l.361-368 | R3 (valida), R1 (ejemplos) | `soil_csv.py`, `services/parcels.py` | `SOIL_CSV_V1`; `parcel_code` = parcela destino | `test_storage_hashing_csv.py`, `test_r1_artifacts.py` (E) | Implementado correctamente |
| RC-S2 Vacío = no medido, nunca cero; método obligatorio | ídem | R3 | `soil_csv.py` | Sin fila de medición | `test_csv_empty_value_means_no_measurement_never_zero` (E) | Implementado correctamente |
| RC-S3/S4 pH [3,10], textura 100 ± 2, fecha no futura | ídem | R3 | `soil_csv.py` | Rangos del catálogo `ref.soil_property`; tolerancia 2 | `test_csv_texture_*`, `test_r1_invalid…` (E) | Implementado correctamente |
| RC-S6 Propiedad sin dato ⇒ `desconocido` | README l.368 | R3 | `soil.property_status` (migración 0008) | Vista `security_invoker` | `test_csv_persist_roundtrip` (E) | Implementado correctamente |
| RC-S5/S7 Activación Modo B; pH medido ⇒ `already_measured` | README §11.1 | R2 | — | — | — | No implementado (R2) |
| RC-D1 Lectura de `curated/<zona>/*.parquet` | README §9, §13.7 | R3 (lee), R1 (escribe) | `storage/parquet.py` | Valida columnas/hash | `test_r1_artifacts.py::…zonal_contract…`, `test_api_analysis.py::…real_r1…` (E) | Implementado correctamente con el contrato **zonal** de R1; difiere del README §13.7 (C-02, ADR-018) |
| RC-D2 QC físico y bit 2 | README §9 | R1 | R1: `milpa_r1.clean_climate` | Anula solo la variable afectada | R1 `selftest` 24/24 (E) | Implementado correctamente (en R1) |
| RC-D4 Lluvia nunca interpolada | README §9 | R1 | R1: `clean_climate` | — | R1 `selftest` (E) | Implementado correctamente (en R1) |
| RC-D5 Relleno ≤ 3 días; HS si falta radiación | README §9 | R1 | R1: `_fill_short_gaps`, `clean_climate` | `HS_KRS=0,16` **[Verificar]** | R1 `selftest` (E) | Implementado correctamente (parámetro pendiente de verificar) |
| RC-D6 Bit 8 (sesgo corregido) | README §9 | R1 | R1 | Definido, **nunca asignado** | — | No implementado |
| RC-D7/D8 Ciclo evaluable por variable; `not_evaluable` | README §11.2 | R2 | — | — | — | No implementado (R2) |
| RC-C2 ET0 FAO-56 PM | README §11.3 | R2 (R1 duplica) | R1: `et0_fao56` | Fórmulas = texto | R1 `selftest` Ej. 18 FAO-56: 3,88 vs 3,9 (E) | Implementado parcialmente (duplicación C-12; sin bandera de ET0 negativo) |
| RC-C3 `ea` por dos rutas/día | README §11.3 | R2 (R1 duplica) | R1: `ea_method` | `R1_dewpoint`/`R2_rh` | R1 `selftest`; `validation_report.json` (E) | Implementado parcialmente (en R1) |
| RC-C4/C5 Pef por decena y propiedades | README §11.4 | R2 (R1 duplica) | R1: `peff_month`, `build_dekad` | 4 métodos; `φ` ausente ⇒ NaN | R1 `selftest` (E) | Implementado parcialmente (en R1) |
| RC-C6 Kc/fenología/umbrales con cita | README §11.5; P9 | R1+R2 | R1: `catalogs/crops.yaml` | Todo `pending` | R1 `validate_catalog` (E) | **Pendiente de validación científica** (SV-02) |
| RC-C7 Asociación: componentes por separado | README §11.5 | R2 | — | — | — | No implementado (R2) |
| RC-C8 Leguminosa ≠ fertilidad por sí sola | README §11.5 | R1/R2 | R1: `fixes_n_conditions: pending` | — | — | Pendiente de validación científica |
| RC-C9/C10 Modelo de estrategia, ciclos, cohortes (DDL) | README §11.6, §13 | R1/R3 | migraciones 0004/0005 | `ref.strategy*`, `strategy_axis_t` | `test_migrations.py`, `test_r3_schema_covers…` (E) | Implementado correctamente (solo esquema) |
| RC-C9/C10 Lógica: fecha ≠ rotación; cohorte; `harvest_date` derivada | README §11.6 | R2 | — | — | — | No implementado (R2) |
| RC-C11 `agri_year_start`, zona, calendario | README §11.6 | R1 | R1: `regions/pilot_corredor_seco.yaml` | `pending` | — | Pendiente de validación científica |
| RC-C12/C13/C15 Cohorte trivalente, Modo A y B | README §11.6-11.8 | R2 | adaptador `adapters/milpa_core.py` | Métodos `PENDING_R2` | `test_adapters_and_static.py` (E, con doble de prueba) | No implementado (R2) |
| RC-C16/C17/C18 Agregación, heatmap, ranking | README §11.9, §11.11 | R2 (+R3 transporta) | `routers/runs.py` | Autorización + `503 DEPENDENCY_NOT_INTEGRATED` | `test_api_analysis.py` (E) | Implementado parcialmente (solo transporte) |
| RC-C14 «No es déficit real del suelo» | README §2, §11.7 | R2/R4 | `contracts/provisional_enums.py` (`Label`) | Etiquetas espejadas | `test_enum_parity.py`, `test_r4_artifacts.py` (E) | Implementado parcialmente (texto lo fija R2) |
| RC-E1 Evidencia = mínimo de insumos | README §21 | R1 (R2 define) | R1: `registrar_procedencia.min_evidence`; R3: `adapters/ports.py::EvidencePort` | R3 **no asigna** evidencia | `test_csv_persist_requires_evidence_port…` (E); `registrar_procedencia` (—) | Implementado parcialmente |
| RC-E2/E3 IMERG ⇒ C sin estación; radiación modelada ⇒ C | README §21 | R1 | R1: `catalogs/evidence_rules.yaml` | «propuesta» | — (no ejecuté `registrar_procedencia.py`: requiere BD de R1) | Pendiente de validación científica (DP-09) |
| RC-E6 Procedencia completa en la respuesta | README §15 | R3 | `services/runs.py::ProvenanceService` | Forma `ProvenanceInfo` | `test_provenance_has_the_shape_of_the_spec_provenance_info` (E) | Implementado correctamente |
| RC-P5 Reproducibilidad por hashes | README §25 | R3 (R1/R2 aportan) | `reproducibility/*` | Hashes canónicos; `make reproduce` exit 2/3 | `apps/api/tests/test_reproducibility.py` (E) | Implementado parcialmente (C-16, sin datos) |
| RC-P8 Paridad de enums | README §5 | R2 (espejo en R3) | `contracts/provisional_enums.py` | 14 enums | `tests/contract/test_enum_parity.py`, `test_r4_artifacts.py` (E) | Implementado parcialmente (espejo provisional) |
| RC-D10 Manifiesto de ingestas | README §9 | R1 | R1: `cargar_manifiesto.py`, `curated_meta.json` | SHA-256 por descarga | — (no ejecutado por R3) | Pendiente de validación |
| RC-U1/U3 La UI no calcula ni afirma de más | README §2 | R4 | R4: `copy-linter.ts` | Linter de textos | Declarado por R4 (D); búsqueda de coordenadas/correos en `src` (E) | Implementado parcialmente (D) |
| RC-U2 Cuatro estados con patrón, no solo color | README §11.9 | R4 | R4: `Heatmap.tsx` | — | Playwright + axe: declarado por R4 (D) | Implementado parcialmente (D) |
| — Fecha de siembra/variedad ≠ rotación en la UI | README §11.6 | R4 | R4: `StrategyCatalog.tsx` | Muestra `changes_from_reference` | — | Implementado parcialmente (sin datos reales) |

## Lectura de la matriz

- **Con prueba ejecutada y sin pendientes:** B1–B6, B8, S1–S4, S6, C9/C10 (esquema), E6, enums.
- **Incompatible hoy:** D1 (Parquet de R1 sin `cell_id`).
- **Sin implementación porque depende de R2:** gating, evaluabilidad de ciclos, asociaciones, cohortes, modos A/B, agregación, heatmap, ranking, escenarios, Soil VoI, `report_model`.
- **Sin cita (no se inventa):** Kc, fenología, umbrales, variedades, calendario, `φ`, tolerancias.
- **Cobertura verificable de las reglas originales:** ver la columna *Evidencia*; las reglas marcadas «—» o «D» no tienen verificación de R3.
