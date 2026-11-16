# Auditoría de R4 — Frontend y producto (FASE 2-3)

> **Actualización posterior (ADR-018):** R1 y R4 se integraron en la raíz del repositorio (`packages/milpa_etl`, `apps/web`, `catalogs/`, `regions/`, `data/`). El contrato Parquet zonal de R1 es ahora el que lee R3 (C-02 resuelto en R3; la diferencia con el README §13.7 queda registrada). Las cifras de este documento corresponden a la auditoría previa a esa integración salvo donde se indique.

Artefacto auditado: `references/R4` (git `ce227a3` + cambios sin confirmar). Método: lectura de documentos y código, comparación programática de su OpenAPI con el de R3, **compilación de su cliente TypeScript contra el OpenAPI de R3** (copia en un directorio temporal; `references/` no se tocó), renderizado de su plantilla de informe a PDF en la imagen Docker de R3.

> R4 **no es una estrategia agronómica** ni define ciencia: la UI muestra lo que entrega el backend y, por regla, no calcula (RC-U3). Las dimensiones agronómicas del encargo (§3) se responden en la sección 3 con evidencia de lo que R4 realmente hace.

## 1. Veredicto resumido

| Aspecto | Resultado | Cómo se comprobó |
|---|---|---|
| Cliente TS de R4 compila contra **su propio** borrador OpenAPI | **0 errores** (`tsc -b`) | ejecutado aquí |
| Cliente TS de R4 compila contra el OpenAPI de **R3** | **302 errores** en ~25 archivos (358 antes de alinear las plantillas de ruta con la especificación) | ejecutado aquí; `matriz_compatibilidad.md` C-17/C-18 |
| Rutas: borrador R4 vs R3 | 34 vs 34 operaciones; **33 coinciden**; única diferencia: `GET /v1/healthz` (R4) vs `GET /healthz` (especificación) | `tests/contract/test_r4_artifacts.py` |
| Enums del borrador vs espejo de la especificación | Idénticos (14 enums) | ídem |
| Plantilla de informe (Jinja2 + CSS) | Renderiza en el entorno restringido de R3; **PDF real de 2 páginas A4** con WeasyPrint 70 | Docker, ejecutado aquí |
| Pruebas propias de R4 (Vitest 26+8, Playwright 25 verdes + 3 `fixme`, build) | **Declaradas por R4; NO re-ejecutadas** por R3 (solo `tsc` sí) | `IMPLEMENTATION_STATUS.md` |
| Integración con el backend real | **No establecida** (R4 lo declara: «la conexión real no se ha probado») | `INTEGRATION_HANDOFF.md` |

R4 es transparente sobre sus límites (borrador local, fixture sintético rotulado, 501 sin fixture aprobado, SPEC-01…06 registrados). La auditoría confirma esa honestidad y mide el costo de la integración.

## 2. Hallazgos (detalle en `matriz_compatibilidad.md`)

| ID | Hallazgo | Quién decide |
|---|---|---|
| C-06 | R4 dibujó `GET /v1/healthz`; la especificación (README §16; R3 §536) fija `GET /healthz` público y sin prefijo. | R4 corrige su borrador |
| C-03 | `DELETE /v1/jobs/{id}`: R4 espera `204` sin cuerpo; R3 devuelve `200` con el trabajo cancelado. La especificación no fija el código. | R3+R4 |
| C-04 | Listados: R4 usa arreglos desnudos (`/zones`, `/catalog/crops`, `/catalog/references`); la especificación de R3 (línea 489) fija `Page[T] = {items, next_cursor}`; R3 pagina. | R4 adapta (spec manda) |
| C-05 | Carga de CSV: R4 espera `200 {accepted[], errors[{row,column,message}]}`; R3 devuelve `200` con conteos por propiedad **o** `422 problem+json` con `errors[{loc,msg,code}]` (todo o nada). La especificación (§16 línea 1549) dice «devuelve errores **o** filas aceptadas por propiedad». | R3+R4 |
| C-11 | SPEC-01 (R4): envolver **toda** cifra en `Indicator` con procedencia, incluidos parámetros de escenario, cobertura, pesos… R4 lo aplica solo en su borrador; el §15 muestra números sueltos en varios DTO. Decisión de contrato de **R2/R3**. | R2 |
| C-17 | ~40 nombres de DTO que R4 importa de `components["schemas"]` (`HeatmapDTO`, `RankResponse`, `StrategyRiskDTO`, `IndicatorNumber`, …) no existen en R3: son `*Payload` opacos `pending_r2` (R3 no puede tipar lo que R2 no ha definido). | R2 define; R3 publica |
| C-18 | Diferencias de forma en endpoints que **sí** son de R3: `RunDTO` (R4 espera `catalog_hash`, `label`, `sandbox`, `synthetic_fixture`), `ParcelDTO` (`display_lat/display_lon` vs `display_location`), `DataQualityDTO` (`sources`, `comparisons`, `ea_sensitivity`, `state`), `ScenariosOut` (envoltorio `{run_id, scenarios[]}` vs arreglo), `SoilCsvResult`. | R3+R4 |
| C-09/C-10 | **Resueltos por R3 en esta auditoría** (ver §5). | — |
| C-14 | La plantilla de R4 espera un contexto (`labels`, `mode`, `strategies`, `ranking`, `annex`…) que debe armar R3 desde el `report_model` de R2 (que no existe). Su `<link href="report.css">` se **perdía en silencio** en el PDF de R3. | R2 define `report_model`; R3 adapta |

## 3. Las dimensiones agronómicas del encargo, aplicadas a R4

| Dimensión | Qué hace R4 | Evidencia |
|---|---|---|
| Objetivo agronómico / tipo de estrategia / secuencia | Ninguno propio. Muestra el catálogo de estrategias (`GET /catalog/strategies`) con `changes_from_reference` y sus ciclos; **un cambio de fecha no se rotula rotación** (lo exige el DTO). | `StrategyCatalog.tsx`, `PRODUCT_TRACEABILITY.md` F07 |
| Calendario, fechas, variedades | No define. `CalendarScreen` representa heatmap y gráfico por decena **recibidos** del backend. | `CalendarScreen.tsx` |
| Requerimientos hídricos / estrés | No calcula. Muestra Modo A/B con la etiqueta del motor y la advertencia «no es agua del suelo». | `RunHeader.tsx`, glosario |
| Parámetros de suelo | Estados por propiedad (`medido/estimado/declarado/desconocido/desactualizado/no_representativo/no_disponible`), subida de CSV, declaraciones; **DTO idéntico** al de R3 (9 de 9 campos). | `SoilComponents.tsx`; comparación de esquemas |
| Criterios de evaluación | Pesos editables con reajuste proporcional (suma 1) en la UI y recálculo por el backend (`POST /rank`); muestra `weight_coverage`, soporte común, `decision_log`. | `weights.ts` |
| Supuestos y limitaciones | Banners de provisionalidad y de fixture sintético; `Indicator` exige valor, unidad, evidencia y procedencia. | `Indicator.tsx` |
| Fuentes | Panel de procedencia con institución y «NASA / No es NASA». | `ProvenancePanel` |
| Reglas de validación | Linter de textos (8 pruebas) contra afirmaciones prohibidas; ESLint; axe sobre 4 pantallas (cubre solo una parte de WCAG). | `copy-linter.ts` |
| Resultados esperados | Cuatro pantallas + informe; T-A·A–J sobre fixture sintético (parte de interfaz). | `tests/acceptance` |

## 4. Verificación del contrato de privacidad y seguridad en el cliente

- Búsqueda en `apps/web/src` de números con ≥ 4 decimales y de correos: 2 coincidencias, ninguna geográfica (una constante de curva Bézier y una tolerancia `0.0001`); 0 correos. El mapa solo dibuja celdas y ubicación generalizada (`display_*`).
- El token se guarda en `sessionStorage` (no `localStorage`): `session.ts`.
- `npm audit` reporta vulnerabilidades en dependencias de **desarrollo** que R4 declara sin revisar (`IMPLEMENTATION_STATUS.md` §8). No se evaluaron aquí.
- Las skills de `.claude/` son herramientas de agente, no producto, y se ignoraron.

## 5. Correcciones hechas en R3 para mantener compatibilidad con R4 (ADR-017)

| Cambio en R3 | Motivo | Efecto medido |
|---|---|---|
| Plantillas de ruta con `{id}`, `{v}`, `{property}` (la URL en ejecución es idéntica) | La especificación escribe así todas las rutas y `openapi-fetch` indexa por plantilla literal | 358 → 302 errores TS |
| `POST /auth/login` añade `expires_in` y `role` (aditivo; se conservan `expires_at`, `token_type`) | `session.ts` de R4 los necesita; ninguna especificación fija el DTO | prueba `test_login_response_is_compatible_with_the_r4_session_client` |
| `GET /reports/{id}/pdf` documenta solo `application/pdf` | Antes anunciaba también `application/json` | prueba de contrato |
| `ProvenanceOut` con los nombres de `ProvenanceInfo` (README §15) | Eran nombres de columnas de BD | prueba `test_provenance_info_field_names_match_the_spec_and_r4` |
| Renderizador incrusta hojas de estilo locales de la carpeta de plantillas | El CSS de R4 se perdía en silencio (sin `base_url`, PDF 14 355 B frente a 18 001 B con estilos) | PDF A4 verificado en Docker |

## 6. Recomendaciones a R4 (sin cambiar sus reglas)

1. Corregir `GET /v1/healthz` → `GET /healthz`.
2. Tratar los listados como `Page[T]` y la carga de CSV como `200`/`422 problem+json` (C-04, C-05) o proponer el cambio por RFC.
3. Importar los tipos de R3 desde el OpenAPI oficial cuando exista; hasta entonces, no depender de nombres de DTO `pending_r2`.
4. Re-ejecutar `npm run web:types` y `tsc -b` contra `docs/openapi/openapi.json` en cada cambio (el comando exacto está en `informe_validacion.md`).
