# Producto, glosario y trazabilidad R4

Estado: especificación funcional derivada del PDF completo; no certifica que el producto esté implementado ni que un requisito esté probado. Se conservan los identificadores documentales F01–F15, X01–X04, UX-01–UX-10 y T-A·A–J.

## Personas usuarias documentadas

| Persona | Necesidad/objetivo recogido en §2 | Preguntas de producto relacionadas |
|---|---|---|
| Técnico agrícola o cooperativa | Entender cambio de calendario, lluvia y exposición en la zona; revisar fuentes y datos faltantes | F01–F06, X04 |
| Técnico agrícola | Determinar si medir pH puede cambiar una decisión | F12, X02 |
| Agricultor/a | Comparar consistencia en años desfavorables según prioridades; explorar fechas y prácticas | F02–F10, F12 |
| Organización | Explorar cómo cambia la comparación bajo escenarios sintéticos especificados | F11 |
| Técnico agrícola y organización | Comparar estrategia y sensibilidad de prioridades | F07–F11 |
| Financiador | Revisar qué evidencia sustenta cada cifra y qué debe verificarse en campo | F13–F14 |

La arquitectura no especifica edad, conectividad, alfabetización digital ni preferencias adicionales de estas personas; no se presuponen en el diseño.

## Historias de usuario derivadas de las preguntas de §2

- **US-01 (F01, F03, F04, F05, X04):** Como técnico de una cooperativa, quiero revisar el historial de 25 años, la cobertura y las decenas de etapas críticas para distinguir lo que muestran los datos de lo que falta.
- **US-02 (F03, F06):** Como técnico o agricultor, quiero comparar fechas de siembra por año y ciclo para entender cuándo la floración cae en decenas críticas, conservando los cuatro estados de datos.
- **US-03 (F02, F07–F10):** Como agricultor, quiero comparar estrategias por ciclo y estrategia, modificar pesos y ver los conflictos para entender cómo cambian las prioridades sin presentar un ganador universal.
- **US-04 (F11):** Como técnico de una organización, quiero explorar perturbaciones históricas sintéticas y comparar su efecto con BASE, viendo parámetros, método, humedad y lectura de adaptación.
- **US-05 (F12, X02):** Como técnico, quiero conocer el estado de cada propiedad del suelo y el valor potencial de medir pH, con valores hipotéticos diferenciados de mediciones.
- **US-06 (F13, F14, X03):** Como técnico, agricultor o financiador autorizado, quiero seguir cada cifra hasta su fuente y recibir un informe que declare limitaciones, faltantes y verificaciones pendientes, con el nivel de privacidad elegido.

## Glosario controlado

Los términos y sus definiciones se resumen de §§2, 11, 15 y 19–21. Deben conservarse en UI, API e informe bilingüe; las etiquetas exactas del motor se muestran desde el DTO.

| Término | Uso controlado |
|---|---|
| Exposición climática al déficit (Modo A) | Diferencia por decena entre demanda del cultivo y precipitación efectiva en etapas críticas; no representa agua real del suelo. Etiqueta oficial: `indicador_exposicion_climatica`. |
| Balance hídrico de la zona radicular (Modo B) | Salida del balance diario de la zona radicular, habilitada solo por los requisitos documentados de suelo, cultivo y condición inicial. Etiqueta oficial: `balance_hidrico_zona_radicular`. |
| Escenario sintético | Perturbación determinista de la serie histórica para explorar sensibilidad; no es pronóstico ni proyección oficial. |
| Cohorte de inicio | Instancia de una estrategia multianual iniciada en un año determinado y evaluada a través de todos sus ciclos. |
| Estrategia | Secuencia versionada de ciclos, componentes y relaciones temporales; se distingue de cambiar solo la fecha o la variedad. |
| Estabilidad del ranking | Sensibilidad del orden frente a variaciones de pesos; no es probabilidad de que una estrategia sea la mejor. |
| Valor hipotético | Valor no medido que se usa para explorar sensibilidad; nunca debe presentarse como dato de una parcela. |
| Procedencia | Fuente, producto e institución, versión, periodo, resolución, método, fecha de recuperación y metadatos asociados al indicador. |
| Evidencia A/B/C | Nivel asignado por regla auditable a cada indicador y limitado por sus entradas; no equivale a certificación externa. |
| `critical` / `non_critical` | Estado decidido del ciclo/cohorte frente al umbral aplicable, no una etiqueta libre de la interfaz. |
| `insufficient_data` | Hay resultados parciales pero la evidencia o lógica disponible no permite decidir el estado. |
| `not_evaluable` | Cobertura de datos insuficiente para evaluar la ventana/ciclo. No se rellena con cero. |
| `provisional` | Resultado que depende de una cita/parámetro pendiente; se acompaña de su razón y advertencia. |
| `weight_coverage` | Suma de pesos de los criterios comunes que participan en el ranking; no se oculta cuando se normalizan pesos efectivos. |

## Correspondencia UX-01–UX-10 con el resto de la arquitectura

| ID conservado | Apartados que completan la tarea | Requisitos adicionales que condicionan R4 | Dependencia/estado inicial |
|---|---|---|---|
| UX-01 | §§2–5, 10, 13, 15–18, 21–22, 24–30 | Personas y preguntas; F01–F15 + X01–X04; glosario; recorrido requisito→pantalla→API/DTO→prueba; limitaciones y decisiones pendientes DP | Documentación R4 posible; el checkout inicial carecía de artefactos |
| UX-02 | §§5, 11, 13, 15, 17, 19, 21–22 | Indicator obligatorio; procedencia/evidencia; enum estable; escenario persistente; ningún cálculo científico en UI; privacidad | Requiere contratos generados R2/R3; no hay tipos locales |
| UX-03 | §§8–9, 13.3–13.4, 16, 18, 20–22, 29 | Estado por propiedad; faltantes no son cero; Soil VoI distingue disponibilidad/aplicabilidad/resultado; pH medido no calcula VoI; sin matriz citada, insuficiente; no geometría exacta | R1 suelo/fuentes, R2 Soil VoI, R3 endpoints/auth; ausentes |
| UX-04 | §§8–12, 15–19, 21, 24, 28–29 | 25 años; unidad por decena/ciclo/cohorte; Modo A/B del motor; Pef sensible a método; etapas citadas; heatmap con cuatro estados y leyenda; escenarios calculados únicamente | R1 series/procedencia, R2 motor, R3 API; ausentes |
| UX-05 | §§4–6, 11.6–11.13, 13, 15–19, 24, 28–30 | Cohortes y estrategia separados de fecha; criterios con estados; soporte común; pesos efectivos/coverage; estabilidad de cuatro estados; escenarios y dependencias; no probabilidades | Catálogos R1, resultados R2, rank/scenario API R3; ausentes |
| UX-06 | §§6, 13, 15–18, 21–22, 24–25, 28–29 | PDF vía backend, hash y `run_id`; página A4 + anexo; bilingüe; `internal`/`public`; advertencias y supuestos; privacidad | Plantilla pertenece a R4; composición y PDF a R3; ausentes |
| UX-07 | §§5, 15, 17, 21–22, 24, 29 | `react-i18next`; teclado/contraste/gráficos; WCAG 2.1 AA es objetivo por verificar; linter incluye excepciones contextuales; etiquetas del motor | Puede prepararse linter/documentación; el proyecto y CI no existen |
| UX-08 | §§24–25, 28–29 | Mantener T-A·A–J y T-P/T-G/T-C/T-I/T-UI/T-S; datos congelados y fixtures rotulados; privacidad por dos usuarios; no falsificar estado de prueba | R1/R2 fixtures y R3 entorno/mocks necesarios; ausentes |
| UX-09 | §§2, 18, 22, 24, 26–30 | Ensayos con técnicos/agricultores solo con acceso y permiso del socio local; sin entrevistas/resultados inventados | Metodología preparada; ejecución externa pendiente |
| UX-10 | §§2–3, 8–9, 17–19, 21–25, 27–31 | Recorrido de cuatro pantallas, demo de solo lectura con datos congelados; separar piloto y fixture sintético; explicar límites; no depender de NASA en demo/CI | Guion posible; demo integrada pendiente de R1–R3 |

## Matriz requisito → usuario → pantalla → componente → endpoint → DTO → aceptación

Los nombres de DTO no explicitados en §15 se marcan como brecha documental; esta matriz no los inventa. Las rutas llevan el prefijo `/v1` definido en §16. Los componentes nombrados son componentes R4 del prompt/§17; donde el documento no asigna uno, se indica “composición de pantalla” para no introducir un contrato visual nuevo.

| Requisito | Usuario | Pantalla | Componentes R4 | Endpoint/entrada | DTO/contrato documentado | Aceptación y pruebas |
|---|---|---|---|---|---|---|
| F01 Historial ~25 años | Técnico/cooperativa | UX-04; calidad en UX-03 | Indicator, EvidenceBadge, ProvenancePanel, Loading, Empty, ErrorState, InsufficientData, ProvisionalBanner | `GET /v1/runs/{id}/climate-history`; `GET /v1/zones/{id}/data-quality` | Resumen de historial no tiene clase DTO nombrada en §15; se debe recibir schema R3 | T-G, T-I, T-P04, T-A·A, T-UI |
| F02 Comparación robusta | Técnico, agricultor | UX-04 y UX-05 | RiskCards, Indicator, ProvenancePanel, ScenarioBadge | `GET /v1/runs/{id}/summary` | `StrategyRiskDTO`, `CycleRiskDTO` | T-A·H, T-P03, T-P07, T-UI |
| F03 Estrés en floración/llenado | Técnico, agricultor | UX-04 | RiskCards, DekadChart, Indicator, ProvisionalBanner, InsufficientData | `GET /v1/runs/{id}/summary`; `GET /v1/runs/{id}/dekad-chart` | `CycleRiskDTO`, `DekadChartDTO`, `Indicator<T>` | T-A·B, T-G, T-UI; umbral sin cita queda provisional/insuficiente |
| F04 Análisis por decena | Técnico/cooperativa | UX-04 | DekadChart, Indicator, ProvenancePanel | `GET /v1/runs/{id}/dekad-chart` | `DekadChartDTO` con `DekadPoint` | T-U, T-P02, T-A·B, T-UI |
| F05 Gráfico Pef vs ETc | Técnico, agricultor | UX-04 | DekadChart, ScenarioBadge, ProvisionalBanner | `GET /v1/runs/{id}/dekad-chart` | `DekadChartDTO`; Pef, ETc y precipitación observada con procedencias separadas | T-A·B, T-UI; línea de asociación solo exploratoria |
| F06 Heatmap fecha × año | Técnico, agricultor | UX-04 | Heatmap, ScenarioBadge, InsufficientData | `GET /v1/runs/{id}/heatmap` | `HeatmapDTO`, `CellState` | T-A·H, T-UI; estados con patrón, texto y leyenda visible |
| F07 Asociaciones y rotaciones | Técnico, agricultor | UX-05 | RiskCards, Heatmap; composición de estrategia por ciclo | `GET /v1/catalog/strategies`; `GET /v1/catalog/strategies/{id}/versions/{v}`; `GET /v1/runs/{id}/summary` | DTO del catálogo/versionado no nombrado; `StrategyRiskDTO` para resultados | T-P08, T-A·H; fecha de siembra no se rotula rotación |
| F08 Ranking multicriterio | Agricultor, técnico | UX-05 | Indicator, EvidenceBadge, TradeoffChart; composición de ranking | `POST /v1/runs/{id}/rank` | `RankRequest`, `RankResponse`, `CriterionCell` | T-P12, T-P13, T-A·I, T-UI |
| F09 Sensibilidad a prioridades | Agricultor | UX-05 | Panel de pesos/controles de pantalla; Indicator para resultados | `POST /v1/runs/{id}/rank` | `RankRequest`, `RankResponse` | T-P06, T-A·E; pesos de entrada suman 1 |
| F10 Estabilidad del ranking | Agricultor, técnico | UX-05 | StabilityMeter, TradeoffChart, Indicator | `POST /v1/runs/{id}/rank` | `RankResponse.stability`, `StabilityDTO`, `StabilityFlag` | T-P06, T-P16, T-A·E; mensaje de interpretación obligatorio |
| F11 Escenarios sintéticos | Técnico/organización | UX-05 | ScenarioPicker, ScenarioBadge, AdaptationToggle, RiskCards, Heatmap | `GET/POST /v1/runs/{id}/scenarios`; `GET /v1/runs/{id}/scenarios` para grilla ya calculada | `ScenarioTag`; contrato de definición/solicitud de escenarios no tiene clase explícita en §15 | T-P05, T-P11, T-A·C; 409 `SCENARIO_NOT_COMPUTED` para combinación ausente |
| F12 Soil VoI | Técnico, agricultor | UX-03 | SoilStatusTable, SoilUpload, VoiPanel, Indicator | `GET /v1/parcels/{id}/soil`; `POST /v1/runs/{id}/soil-voi`; carga/declaración de suelo | `SoilPropertyStatusDTO`, `SoilVoiResponse`, `Hypothetical` | T-P09, T-P10, T-A·A, T-A·D; `already_measured` no produce estabilidad |
| F13 Procedencia y evidencia | Todos según acceso | Las cuatro | Indicator, EvidenceBadge, ProvenancePanel, ProvisionalBanner | `GET /v1/provenance/{ip_id}` | `Indicator<T>`, `ProvenanceInfo`, `SourceRef` | T-P14, T-C, T-UI, CT-01/03 |
| F14 Informe de decisión | Técnico, dueño, financiador | UX-06 | Composición de informe; Indicator y ProvenancePanel en vista previa | `POST /v1/reports`; `GET /v1/reports/{id}`; `GET /v1/reports/{id}/pdf` | `ReportDTO`, `ReportSection` | T-A·F, T-S; PDF con anexo, resumen inglés, referencias, hash y privacidad |
| F15 Reproducibilidad | Técnico, organización/financiador | UX-06 y UX-10; CLI fuera de UI | ScenarioBadge en artefactos mostrados; composición de estado de hashes | `data/demo/`, `EXPECTED.json`, `make demo`, `make reproduce`; no endpoint de UI definido | Identificadores `run_id`, `code_version`, `region_config_hash`, `catalog_hash`, `data_hash`, `params_hash`, `seed` | T-A·G, T-I; demo sin NASA, datos congelados |
| X01 Separación de modos | Todos | UX-04 y UX-05 | Indicator, ProvisionalBanner, InsufficientData | `GET /v1/runs/{id}` | `Mode`, `Label`; DTO de corrida no nombrado en §15 | T-A·A, T-P15; motor determina modo y razones |
| X02 Suelo por propiedad/CSV | Agricultor, técnico asignado | UX-03 | SoilStatusTable, SoilUpload, Indicator, ErrorState | `GET /v1/parcels/{id}/soil`; `POST /v1/parcels/{id}/soil-samples`; `PUT /v1/parcels/{id}/soil-declarations/{property}` | `SoilPropertyStatusDTO`; respuesta de carga con errores por fila no nombrada | T-P10, T-I, T-UI; vacío significa no medido |
| X03 Privacidad de parcelas | Agricultor, técnico asignado | UX-03, UX-06 | Estados de carga/error; la privacidad debe garantizarla API y presentación | `POST/GET/DELETE /v1/parcels`; informe public por `/v1/reports` | DTOs de parcela/consentimiento no nombrados en §15 | T-S, T-A·J; pertenencia, borrado y cero datos privados públicos |
| X04 Ingesta/calidad | Técnico/cooperativa | UX-03 y UX-04 | Indicator, EvidenceBadge, ProvenancePanel, InsufficientData | `POST /v1/zones`; `GET /v1/zones/{id}/data-quality` | Resultado de ingesta/calidad no nombrado en §15 | T-I, T-P04, CT-11/12; demo/CI no llama NASA |

### Estados comunes y sus criterios

Todas las pantallas UX-03–UX-06 deben tener estados `loading`, `empty`, `error` (código y orientación), `insufficient_data` (qué falta y cómo obtenerlo) y `provisional` (parámetro/cita pendiente y advertencia). Un estado no se interpreta desde un valor numérico nulo ni se sustituye por cero. Deben existir textos y patrones no dependientes únicamente del color.

## Pendientes que no se pueden resolver en la UI

- DP-01–DP-03: zona real, cultivos/variedades y calendarios locales.
- DP-04–DP-05: Kc, fenología, etapas críticas y umbrales con citas (R1/R2 y asesor).
- DP-06–DP-09: método Pef, onset/adaptación, faltantes y umbrales de comunicación.
- DP-10–DP-12: matriz de pH, datos y parámetros para Modo B/VoI.
- DP-13–DP-17: privacidad/consentimiento, licencias, socio/asesor, productos externos y tolerancias de referencia.

Hasta recibir acuerdos y contratos, estos campos siguen `pending`/sandbox o se expresan como no disponibles. La interfaz no los decide.

> **Actualización 2026-11-15:** las brechas de la tabla siguiente que dependían solo de la interfaz (historial, calidad, catálogo, trabajos, subida de suelo, declaraciones, borrado, inversiones, bandas de etapa, acumulado, mapa) se implementaron sobre el borrador de contrato ampliado y se verifican con el fixture sintético. El estado vigente y lo que sigue pendiente está en `IMPLEMENTATION_STATUS.md`.

## Progreso de implementación R4 — 2026-11-14

El estado inicial de las filas anteriores refleja la auditoría previa a código. Después se construyeron pantallas parciales contra el borrador local de R4. Esta lista no altera el estado de autorización ni la fuente del contrato:

| Pantalla | Rutas documentadas consumidas | DTO usado en el borrador | Qué está visible | Brechas que siguen bloqueando aceptación |
|---|---|---|---|---|
| Mi zona | `GET /v1/zones`, `GET /v1/zones/{id}`, `GET /v1/zones/{id}/data-quality`, `GET /v1/parcels/{id}/soil`, `POST /v1/runs/{id}/soil-voi` | `ZoneSummaryDTO`, `ZoneDTO`, `SoilPropertyStatusDTO`, `SoilVoiResponse` | Selector de zonas, fuentes, indicadores de elevación/pendiente, estados de suelo y consulta de Soil VoI | DTO de calidad/contexto, listado de parcelas, multipart CSV, declaraciones y privacidad de sesión no entregados |
| Calendario | `GET /v1/runs/{id}/scenarios`, `/summary`, `/climate-history`, `/heatmap`, `/dekad-chart` | `ScenarioTag`, `StrategyRiskDTO`, `HeatmapDTO`, `DekadChartDTO` | Escenario calculado, filtros URL, riesgos, estados de heatmap y decenas con Indicators/procedencia | DTO historial, cohortes/base, stage bands/cumulative y etiquetas R2 no confirmadas |
| Rotaciones | `GET /v1/runs/{id}/scenarios`, `/summary`; `POST /v1/runs/{id}/rank` | `RankRequest`, `RankResponse`, `StabilityDTO`, `StrategyRiskDTO` | Cuatro pesos, suma 1, soporte común, ranking, cobertura y estabilidad | `StabilityRequest`, IDs/filas, conflictos y decision log pendientes de R2/R3; body vacío de estabilidad es solo borrador local |
| Informe | `POST /v1/reports`, `GET /v1/reports/{id}`, `GET /v1/runs/{id}`; vínculo al PDF en `ReportDTO.pdf_url` | `ReportRequestDraft`, `ReportDTO`, `ReportSection` abierto, respuesta de corrida abierta | Privacidad, idioma, plantilla bilingüe, hashes conocidos de §25 si aparecen en la corrida y enlace al PDF backend | Job, secciones completas, vínculo de hashes al PDF, anonimización y PDF no verificados |

`apps/web/src/api/types.gen.ts` se genera desde `contracts/openapi.v0.draft.yaml` en build; no existe archivo generado hasta que se instalen dependencias. Ninguna cifra de piloto se agrega desde R4. Las pruebas T-A·A–J permanecen pendientes de los fixtures congelados R1/R2 y no se reportan como verdes.
