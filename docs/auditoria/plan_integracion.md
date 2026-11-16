# Plan de integración (FASE 5-6)

> **Actualización posterior (ADR-018):** R1 y R4 se integraron en la raíz del repositorio (`packages/milpa_etl`, `apps/web`, `catalogs/`, `regions/`, `data/`). El contrato Parquet zonal de R1 es ahora el que lee R3 (C-02 resuelto en R3; la diferencia con el README §13.7 queda registrada). Las cifras de este documento corresponden a la auditoría previa a esa integración salvo donde se indique.

Qué se **ejecutó** en esta auditoría, qué queda por hacer y qué decisiones no puede tomar R3. Orden de prioridad: seguridad → contratos definidos por la especificación → contratos sin definir → ciencia.

## 1. Hecho en R3 (verificado; ver `informe_validacion.md`)

| # | Cambio | Justificación | ADR |
|---|---|---|---|
| 1 | Guardia de arranque de invariantes de seguridad (`api/db/invariants.py`) | S-01: un script ajeno puede evadir RLS | ADR-017 |
| 2 | CSV de suelo conforme al README §9 (`SOIL_CSV_V1`) | C-15: R3 había inventado un contrato existente | ADR-017 |
| 3 | `ProvenanceOut` → forma de `ProvenanceInfo` (§15) | La especificación lo define | ADR-017 |
| 4 | Plantillas de ruta con `{id}`/`{v}`/`{property}` | La especificación las escribe así; clientes tipados | ADR-017 |
| 5 | Login con `expires_in` y `role` (aditivo) | Consumo de R4; DTO no definido por la especificación | ADR-017 |
| 6 | `/reports/{id}/pdf` solo `application/pdf` | Exactitud del contrato | ADR-017 |
| 7 | `render_template_pack` + `inline_local_stylesheets` | Usar la plantilla de R4 sin perder el CSS ni abrir la red | ADR-017 |
| 8 | Suites de compatibilidad con artefactos reales: `tests/contract/test_r1_artifacts.py`, `test_r4_artifacts.py` | Que la compatibilidad sea verificable en cada cambio | — |

## 2. Acciones pendientes por responsable

### R1
| Prioridad | Acción | Referencia |
|---|---|---|
| **Alta** | Corregir `92_soil_fixture_provenance.sql` con `WITH (security_invoker = true)`; no ejecutar DDL sobre la base compartida (la cadena Alembic de R3 es la única) | S-01 |
| Alta | Decidir con R2/R3 el esquema de Parquet (¿`cell_id`?, `tmean_c`, `obs_date` fecha) y actualizar README §13.7 o los archivos | C-02 |
| Media | Entregar `data/demo/` y `EXPECTED.json` (sin coordenadas ni datos personales); definir cómo disparar la ingesta sin importar `milpa_etl` | R3-F21/F22, C-16 |
| Media | Ordenar los SQL para aplicarse por nombre o entregarlos como revisiones | C-01 |
| Media | Declarar la regla `soil_fixture_c` o dejar de usarla; limitar `ingestar_suelo_db.py` a fixtures | C-13 |
| Baja | Bandera de ET0 negativo; aclarar `fallback_share_pct`; confirmar `ip_id NOT NULL` | SV-04, SV-03, C-07 |

### R2 (no existe)
| Prioridad | Acción |
|---|---|
| **Alta** | Entregar `milpa_core` con `enums`, la fachada de 5 funciones, errores tipados, DTO de resultado (Heatmap, Dekad, StrategyRisk, Rank, Scenarios, SoilVoi) y `ReportModel` |
| Alta | Decidir si ET0/Pef viven solo en `milpa_core` y R1 deja de calcularlos (C-12) |
| Alta | Definir `Indicator` para toda cifra (SPEC-01 de R4, C-11) y las estructuras que el §15 deja sin campos (SPEC-02) |
| Media | Reglas de evidencia A/B/C (`EvidencePort`) para poder **guardar** mediciones de suelo |
| Media | Decisión sobre la lluvia primaria y la corrección de sesgo (SV-01) |

### R4
| Prioridad | Acción |
|---|---|
| Alta | `GET /v1/healthz` → `GET /healthz` (C-06) |
| Alta | Adaptarse a `Page[T]`, a la carga de CSV `200`/`422` y a los DTO de R3 que ya existen (C-04, C-05, C-18) o abrir RFC |
| Media | Regenerar tipos desde `docs/openapi/openapi.json` en cada cambio y mantener `tsc -b` en CI (comando en `informe_validacion.md`) |
| Media | Armar el contexto de la plantilla desde `report_model` cuando exista (C-14) |

### R3 (pendiente propio)
| Prioridad | Acción |
|---|---|
| Alta | Decidir con R4 el código de `DELETE /jobs/{id}` (C-03) y la forma de `RunOut`/`ParcelOut`/`DataQualityOut`/`ScenariosOut` (C-18) |
| Alta | Aprobación de ADR-003, 007, 009, 010, 015, 016, **017** |
| Media | Cuando llegue el Parquet definitivo de R1, ajustar `ParquetContract` y quitar los 3 `xfail` |
| Media | Equivalencia de `data_hash` con R1 cuando exista `EXPECTED.json` (C-16) |
| Baja | Endpoints de consentimiento y registro de usuarios cuando el contrato exista |

## 3. Decisiones que requieren confirmación (no se tomaron)

| Decisión | Opciones | Quién | Efecto si no se decide |
|---|---|---|---|
| Parquet por zona o por celda (C-02) | (a) R1 añade `cell_id` y `tmean_c`; (b) la especificación se corrige a serie por zona; (c) R3 acepta ambas con un contrato versionado | R1+R2+R3 | R3 sigue respondiendo 503 `DATASET_INCOMPATIBLE`; sin serie no hay corrida real |
| Lluvia primaria y sesgo (SV-01) | POWER con limitación explícita / IMERG con ventana más corta / corrección con estación | R2+asesor | La serie de 25 años mezcla dos productos (81 % / 19 %) |
| `Indicator` en toda cifra (C-11) | Adoptar SPEC-01 de R4 / mantener números sueltos de §15 con excepción documentada | R2+R3 | R4 y el backend no pueden fijar DTO de escenarios/cobertura |
| Cancelación de trabajos (C-03) y `Page[T]` en listados (C-04) | 204 vs 200; arreglo vs página | R3+R4 | El cliente tipado no compila en esos endpoints |
| Política de acceso/retención (DP-13) | Pendiente | Equipo legal/socio | Sin datos personales reales; admin no puede borrar parcelas |

## 4. Lo que NO se hará sin autorización

- Definir estrategias, cultivos, Kc, fenología, umbrales, calendarios o variedades.
- Reimplementar ET0/Pef/ranking en el backend para «completar» los endpoints de análisis.
- Modificar `references/` (propiedad de R1 y R4).
- Marcar una interfaz como `integrated` o `verified` sin ejecutarla contra el componente real (`docs/integration/INTEGRATION_STATUS.md`).
