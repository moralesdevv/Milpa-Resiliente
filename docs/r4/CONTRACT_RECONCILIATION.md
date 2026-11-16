# Reconciliación de contratos — especificación MILPA RESILIENTE 3.3

Estado: discrepancias documentales para resolver con R2/R3. Este registro no cambia ningún contrato oficial.

## SPEC-01 — Cifras de presentación fuera de `Indicator`

**Fuentes:** §5/P2, §15 (`Indicator`), §17 (regla 1), §21 y criterio transversal CT-01 en §29.

La regla transversal dice que toda cifra presentada debe viajar dentro de un `Indicator` con procedencia y nivel A/B/C. Sin embargo, varios DTOs de §15 incluyen números escalares/listas fuera de `Indicator`, entre ellos:

- `ScenarioTag`: `delta_t_c`, `precip_factor`, `onset_delay_days`.
- `Coverage`/`ProvenanceInfo`: conteos, `missing_pct` y `CycleRiskDTO.peff_sensitivity`.
- `HeatmapDTO`: `severity`, `pct_critical_by_date` y `n_decided_by_date`.
- `DekadChartDTO`: `etc_system_exploratory` (float nullable, solo asociativo).
- `RankResponse`: `weight_coverage`, `top_margin`, valores de tabla parcial y medidas de estabilidad.
- `SoilPropertyStatusDTO`: `depth_cm`, `age_years`, `max_age_years`.
- `SoilVoiResponse.Hypothetical`: valor hipotético.

Algunos son metadatos de configuración o cobertura, y el documento no establece si CT-01 los exceptúa o cómo se envuelve cada uno con procedencia. La UI puede abstenerse de inventar procedencia, pero no puede cumplir simultáneamente ambas formas de contrato sin decisión.

**Decisión del borrador local R4:** los valores numéricos que se renderizan se expresan como `Indicator`, incluidos parámetros sintéticos, cobertura, sensibilidad a Pef, celdas de severidad, porcentaje/conteo por fecha, serie exploratoria ETc, valores del ranking, propiedades hipotéticas y `ProvenanceInfo.missing_pct`. Este último es opcional dentro de `ProvenanceInfo`; el propio indicador de faltantes puede omitir su porcentaje faltante para evitar una recursión de datos. Así la UI puede exigir valor, unidad, evidencia y procedencia de una sola forma. Fechas, ejes de año, IDs, pesos que la persona está editando y códigos de estado son contexto/controles, no resultados medidos.

Esta resolución se aplica solo en `openapi.v0.draft.yaml`; cambia la representación de varios campos respecto del ejemplo de §15. Se propone a R2/R3 como manera de cumplir P2/CT-01 sin excepciones para cifras resultantes. No cambia ningún contrato oficial y requiere conciliación antes de integrarse con sus respuestas.

## SPEC-02 — DTOs citados sin estructura completa

**Fuente:** §15, contrastado con rutas y respuestas de §16.

El documento nombra, pero no define campos de, entre otros: `SourceRef`, `Period`, `Coverage`, `Sensitivity`, `WaterInputs`, `DekadPoint`, `StageBand`, `CumPoint`, `DekadProvenance`, `Weights`, `StabilityRequest`, `StabilityDTO`, `RankedStrategy`, `CriterionCell`, `PartialRow`, `Decision`, `PairExplanation`, `Hypothetical` y varias respuestas de zona, corrida, carga CSV y job. En particular, el resumen de `RankResponse` describe `rank`, `total` y `criteria`, pero no aclara cómo se identifica la estrategia en cada fila. Las rutas sí están listadas; la forma de algunas solicitudes/respuestas no.

**Tratamiento:** un esquema derivado puede tipar solo los campos explícitos y dejar el resto abierto/pendiente. No se rellenarán campos faltantes ni se presentará un esquema derivado como el OpenAPI oficial de R3.

## SPEC-03 — Prefijo de rutas

El prompt maestro usa rutas de ejemplo sin prefijo; §16 define la API REST bajo `/v1`. Cualquier contrato de trabajo conservará `/v1` como está escrito en el PDF. El prefijo no es una ruta nueva.

## SPEC-04 — `Indicator` genérico en OpenAPI

§15 define `Indicator[T]` en Pydantic y exige su uso desde cualquier número presentado. OpenAPI no representa directamente el genérico Python; la generación deberá producir esquemas concretos para cada tipo de valor sin copiar tipos a mano en el frontend. R2/R3 deberán confirmar nombres/estructura reales al entregar el esquema oficial.

## SPEC-05 — Trazabilidad y hashes del informe

**Fuentes:** §§13, 18, 21 y 25; UX-06 y UX-10 del prompt maestro.

El contenido de informe requiere `run_id` y hashes de reproducibilidad disponibles (`code_version`, `region_config_hash`, `catalog_hash`, `data_hash`, `params_hash` y semilla). El `ReportDTO` en §15 documenta `run_id`, `pdf_url` y `sha256` del PDF, pero no define cómo obtener ni asociar los hashes de la corrida ni un esquema completo de secciones.

**Tratamiento R4:** la pantalla solicita el PDF a R3 y presenta `run_id`, secciones y `sha256` cuando están en `ReportDTO`. También consulta `GET /v1/runs/{id}` y solo muestra los cinco hashes/código-versiones conocidos de §25 cuando aparecen como cadenas en la respuesta. No fabrica los hashes ausentes ni compone el PDF localmente. R3 debe confirmar el vínculo al DTO de corrida/reproducibilidad y los campos de sección antes de aceptar UX-06 como completo.

## SPEC-06 — Contexto de zona, calidad y parcelas

**Fuentes:** §§13.3–13.4, 15–16 y 18; UX-03 y UX-04.

`ZoneDTO` recibe en §15 una lista de fuentes, pero no define celdas/clima, contexto de cultivos y temporadas, ni el contrato de cobertura/calidad. Las rutas previstas para calidad existen en §16; la respuesta detallada no. Tampoco se define una ruta para listar parcelas de una zona. La arquitectura prohíbe exponer geometría exacta de parcela.

**Tratamiento R4:** la pantalla consume zona, calidad y suelo por sus rutas documentadas; deja visibles los campos no descritos como insuficientes/pendientes. El ID de parcela se ingresa explícitamente porque no hay contrato de lista. No se dibuja un mapa con geometría no disponible ni se exponen coordenadas de parcela.

## Regla temporal de integración

La instrucción posterior del usuario es continuar según el mejor juicio siguiendo la estructura dada. Se permite crear artefactos locales derivados para avanzar, siempre etiquetados como borrador. Al recibir OpenAPI/DTOs oficiales, se compararán contra SPEC-01–SPEC-04 y `PRODUCT_TRACEABILITY.md`; cualquier cambio seguirá el proceso de RFC/versionado indicado en §27. Ningún borrador local se describirá como firmado o validado por R1/R2/R3.
