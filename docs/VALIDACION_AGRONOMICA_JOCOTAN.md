# Validación agronómica y climática — Jocotán (Chiquimula)

> **Estado: PROVISIONAL.** Todos los parámetros son referencias pendientes de validación oficial MAGA/ICTA y de calibración local.
> Nada de lo que muestra la aplicación es una recomendación oficial ni una alerta operativa.

## 1. Qué se implementó
| Pieza | Dónde |
|---|---|
| Fuente central de parámetros | `regions/reglas_agronomicas_jocotan.json` (v2.0.0). Se generó con `tools/agronomy/build_rules_json.py`; **para cambiar valores se edita el JSON**, no el código |
| Carga con errores controlados | `apps/api/src/api/agronomy/rules.py` (archivo ausente o mal formado → 503 solo en estos endpoints; el resto de la API sigue) |
| Validación de siembra | `agronomy/validation.py::validar_siembra` → `GET /v1/zones/{id}/planting-validation` |
| Inicio de lluvias (sandbox) y retraso | `agronomy/onset.py::detectar_inicio_lluvias` y `evaluar_retraso_adaptacion` → `GET /v1/zones/{id}/rainy-season-onset` |
| Validación con estación Camotán | `agronomy/station.py::validar_con_estacion_local` → `GET /v1/zones/{id}/station-validation` |
| Opciones del formulario | `GET /v1/zones/{id}/planting-options` (salen del JSON) |
| Interfaz | `apps/web/src/components/zone/PlantingValidation.tsx`, `RainyOnsetSandbox.tsx`, `StationValidationNotice.tsx`, `AgronomyKinds.tsx`, en «Mi zona» (el aviso de evidencia también en el MVP) |
| Mensajes es/en | `agronomy/i18n.py` (parámetro `idioma=es\|en`) |
| CSV de ejemplo (FICTICIO) | `data/estaciones/camotan_ejemplo.csv` |

## 2. Metodología
1. **Fenología.** Se buscaron ciclos y floración por variedad en fuentes primarias (ICTA, FAO). Cuando solo existe el ciclo total, las etapas FAO (inicial, desarrollo, media, final) se **derivan** repartiendo ese total con las proporciones de la Tabla 11 de FAO-56 (método del mayor resto, suma exacta; una prueba comprueba que la suma de etapas = ciclo). Si no se encontró ciclo, se usa la fila FAO-56 de maíz grano de 125 d como **proxy rotulado**, nunca como medición de ICTA.
2. **Kc.** Son proxies FAO-56 Tabla 12 (maíz grano: 0.30 / 1.20 / 0.35; frijol seco: 0.40 / 1.15 / 0.35), con interpolación lineal en desarrollo y final. No existe Kc medido por variedad ICTA en las fuentes consultadas. FAO-56 da Kc fin del maíz 0.60 si se cosecha con humedad alta; se usa 0.35 (secado completo en campo). No se aplicó ajuste climático (HRmin/viento) porque POWER no entrega HRmin.
3. **Validación de siembra.** Cultivo y variedad permitidos, ciclo válido, fecha dentro de la ventana (límites inclusivos), días secos ≥ umbral → alerta de sequía, lluvia de 15 días < mínimo → alerta. Una fecha fuera de ventana es una advertencia de compatibilidad con el calendario, **no una prohibición**. Los umbrales hídricos son los provistos por el equipo (sandbox, sin cita agronómica).
4. **Inicio de lluvias.** Criterio de pentadas del Informe No. 6 de MAGA (8-may-2025, datos INSIVUMEH/ICC, adaptado de Alfaro, Cid y Enfield 1999): pentada ≥ 25 mm y una o ambas de las dos siguientes también; pentadas previa y siguientes > 0.5 mm. Texto leído directamente del PDF. **No es un procedimiento metodológico propio de INSIVUMEH** (no se localizó) y la redacción sobre las pentadas «anteriores y posteriores» es ambigua: aquí se exige > 0.5 mm en la previa y en las dos siguientes (modo estricto `ambas_siguientes` disponible en el JSON). Los días sin dato nunca se tratan como cero: una pentada incompleta no es evaluable. Las pentadas se fijan por fecha de calendario desde el 1 de enero (73 por año; el 29-feb se suma a la pentada 12).
5. **Estación Camotán.** Sin CSV real el estado es «Nivel C - Pendiente». Con un CSV real (`fecha,precipitacion_mm`, mm/día) se calculan RMSE, sesgo (satélite − estación) y r de Pearson **solo con fechas coincidentes**; el Nivel B exige ≥ 365 días coincidentes (configurable) y correlación calculable. El Nivel B significa validación del producto (IMERG) y periodo evaluados, no de todo el sistema. El CSV de ejemplo, o cualquier archivo marcado como ficticio, **nunca** cambia el estado.

## 3. Tabla maestra de parámetros fenológicos y Kc
| Cultivo | Variedad | Etapa FAO | Duración (días) | Kc | Fuente | Confianza | Tipo de dato | Supuesto aplicado |
|---|---|---|---:|---|---|---|---|---|
| maiz | ICTA B-7 | Inicial | 19 | 0.30 | ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo 4 meses (ICTA 2015) = 120 d con 30 d/mes; etapas repartidas con las proporciones 20/35/40/30 de FAO-56 Tabla 11 (maíz, 125 d). Kc = pr… |
| maiz | ICTA B-7 | Desarrollo | 34 | 0.30 → 1.20 | ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo 4 meses (ICTA 2015) = 120 d con 30 d/mes; etapas repartidas con las proporciones 20/35/40/30 de FAO-56 Tabla 11 (maíz, 125 d). Kc = pr… |
| maiz | ICTA B-7 | Media | 38 | 1.20 | ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo 4 meses (ICTA 2015) = 120 d con 30 d/mes; etapas repartidas con las proporciones 20/35/40/30 de FAO-56 Tabla 11 (maíz, 125 d). Kc = pr… |
| maiz | ICTA B-7 | Final | 29 | 1.20 → 0.35 | ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo 4 meses (ICTA 2015) = 120 d con 30 d/mes; etapas repartidas con las proporciones 20/35/40/30 de FAO-56 Tabla 11 (maíz, 125 d). Kc = pr… |
| maiz | ICTA B-5 | Inicial | 14 | 0.30 | ICTA_PROGRAMA_MAIZ, ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo precoz de 90 d (ICTA, página del programa; 3 meses en ICTA 2015); etapas con proporciones FAO-56 Tabla 11. Kc = proxy FAO-56.… |
| maiz | ICTA B-5 | Desarrollo | 25 | 0.30 → 1.20 | ICTA_PROGRAMA_MAIZ, ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo precoz de 90 d (ICTA, página del programa; 3 meses en ICTA 2015); etapas con proporciones FAO-56 Tabla 11. Kc = proxy FAO-56.… |
| maiz | ICTA B-5 | Media | 29 | 1.20 | ICTA_PROGRAMA_MAIZ, ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo precoz de 90 d (ICTA, página del programa; 3 meses en ICTA 2015); etapas con proporciones FAO-56 Tabla 11. Kc = proxy FAO-56.… |
| maiz | ICTA B-5 | Final | 22 | 1.20 → 0.35 | ICTA_PROGRAMA_MAIZ, ICTA_MAIZ_ORIENTE_2015, FAO56 | media-baja | derivado | Ciclo precoz de 90 d (ICTA, página del programa; 3 meses en ICTA 2015); etapas con proporciones FAO-56 Tabla 11. Kc = proxy FAO-56.… |
| maiz | ICTA B-9 | Inicial | 20 | 0.30 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-9 | Desarrollo | 35 | 0.30 → 1.20 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-9 | Media | 40 | 1.20 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-9 | Final | 30 | 1.20 → 0.35 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-15 | Inicial | 20 | 0.30 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-15 | Desarrollo | 35 | 0.30 → 1.20 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-15 | Media | 40 | 1.20 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| maiz | ICTA B-15 | Final | 30 | 1.20 → 0.35 | FAO56 | baja | proxy FAO-56 | NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125… |
| frijol | ICTA Ostúa | Inicial | 15 | 0.40 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Ostúa | Desarrollo | 24 | 0.40 → 1.15 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Ostúa | Media | 22 | 1.15 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Ostúa | Final | 12 | 1.15 → 0.35 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Santa Gertrudis | Inicial | 15 | 0.40 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Santa Gertrudis | Desarrollo | 24 | 0.40 → 1.15 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Santa Gertrudis | Media | 22 | 1.15 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |
| frijol | ICTA Santa Gertrudis | Final | 12 | 1.15 → 0.35 | ICTA_FRIJOL_2011, FAO56 | media | derivado | Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrol… |

Los supuestos completos están en el JSON (`supuesto_aplicado`, `supuestos_generales`). Valores en conflicto para ICTA B-7: ciclo 95 d (guía general ICTA, registro previo) · 110 d a cosecha (Memoria ICTA 2002, registro previo) · **120 d** (ICTA 2015, oriente; usado).

**Variedades sin dato de ciclo (NO ENCONTRADO):** ICTA B-9 e ICTA B-15 (la página del programa de maíz de ICTA no publica ciclo ni floración). Se usa el proxy FAO-56 y la interfaz lo advierte.

## 4. Fuentes consultadas
- **FAO56** — FAO Irrigation and Drainage Paper 56, cap. 6: Tabla 11 (duración de etapas) y Tabla 12 (Kc únicos) (FAO). https://www.fao.org/4/x0490e/x0490e0b.htm. _Kc ini de maíz está en una imagen de la tabla: valor 0.30 de la tabla publicada, no leído por extracción de texto; verificar contra el original._
- **ICTA_MAIZ_ORIENTE_2015** — Recomendaciones técnicas para el cultivo de maíz en el oriente de Guatemala (Chiquimula, El Progreso, Jalapa, Jutiapa, Santa Rosa, Zacapa; 100-1400 msnm) (ICTA, 2015-12). https://www.icta.gob.gt/publicaciones/Maiz/Recomendaciones%20tecnicas%20para%20el%20cultivo%20de%20maiz%20en%20el%20oriente%20de%20Guatemala%202015.pdf. _Ciclo de ICTA B-5 (3 meses) e ICTA B-7 (4 meses) para lugares con escasez de lluvia; siembra a finales de mayo o inicios de junio._
- **ICTA_PROGRAMA_MAIZ** — Programa de maíz: variedades ICTA B-1, B-5 (ciclo precoz 90 días), B-7TS (tolerante a sequía), B-9ACP, B-15ACP+Zn (ICTA). https://www.icta.gob.gt/programademaiz.html. _La página no da días a floración ni madurez de ninguna variedad; B-9 y B-15 sin ciclo._
- **ICTA_FRIJOL_2011** — Producción de frijol Phaseolus vulgaris L. (ICTA/FAO), Cuadro 1: características agronómicas de variedades mejoradas (ICTA / FAO, 2011). https://www.icta.gob.gt/publicaciones/Frijol/Produccion%20de%20Frijol%20Phaseolus%20vulgaris%20L%202011.pdf. _Ostúa y Santa Gertrudis: días a floración 38-40, días a cosecha 70-75, adaptación 50-1200 msnm, recomendadas para Sur, Oriente y Norte. Leído de la imagen escaneada (p. 4)._
- **ICTA_MEMORIA_2002** — Memoria de labores 2002 (floración de ICTA B-7 = 53 d e ICTA B-5 = 48 d en ensayos) (ICTA, 2002). https://www.icta.gob.gt/publicaciones/Memoriasicta/Memoria%20de%20labores%202002.pdf. _Valores registrados en una pasada previa (catalogs/r2/reference/web_sourced_crops.yaml); NO re-verificados en esta pasada (PDF escaneado de muchas páginas)._
- **MAGA_INFORME_6_2025** — Informe No. 6 (8 de mayo de 2025): criterio de pentadas para establecer la temporada lluviosa, con datos de INSIVUMEH e ICC (MAGA - DIGEGR / CIEA, 2025-05-08). https://www.maga.gob.gt/download/informe6-25.pdf. _Texto leído directamente. Es un criterio operativo de MAGA que usa datos INSIVUMEH/ICC (adaptado de Alfaro, Cid y Enfield, 1999); no es un documento metodológico de INSIVUMEH._
- **MAGA_EPOCAS** — Épocas de siembra y cosecha de cultivos agrícolas de Guatemala (MAGA). https://www.maga.gob.gt/download/epocas-siembra-cosecha-agricolas-guatemala.pdf. _Contexto nacional/regional; las fechas de Jocotán de este JSON son provisionales._
- **USUARIO_SANDBOX** — Reglas y umbrales provisionales proporcionados por el equipo del proyecto (MILPA RESILIENTE). sin URL. _Sin cita agronómica; requieren validación MAGA/ICTA._

No se pudo re-verificar en esta pasada: la Memoria ICTA 2002 (escaneo de muchas páginas); el Kc inicial del maíz de FAO-56 está en una imagen de la tabla (valor 0.30 de la tabla publicada, verificar contra el original).

## 5. Estado de evidencia
| Elemento | Estado |
|---|---|
| Ventanas de siembra, umbrales hídricos, rango de temperatura | **Provisional** (sin cita agronómica; reglas del equipo) |
| Ciclo/floración de frijol ICTA Ostúa y Santa Gertrudis | Encontrado en ICTA/FAO 2011, Cuadro 1; etapas derivadas |
| Ciclo de maíz ICTA B-5 / B-7 | Encontrado (90 d / «cuatro meses»); etapas derivadas |
| Ciclo de maíz ICTA B-9 / B-15 | NO ENCONTRADO — proxy FAO-56 |
| Kc | Proxy FAO-56 (no medido por variedad) |
| Precipitación satelital vs. estación | **Nivel C — validación local pendiente** |
| Inicio de lluvias | Escenario sandbox, no usar para decisiones operativas |

## 6. Cómo actualizar los parámetros sin tocar el código
1. Edite `regions/reglas_agronomicas_jocotan.json` (ventanas en `ventanas_siembra`, umbrales en `cultivos.<cultivo>.umbrales_hidricos`, criterio de pentadas en `inicio_lluvias`, estación en `estacion_local`). `tools/agronomy/build_rules_json.py` solo sirvió para generar la primera versión con las sumas de etapas verificadas; no hace falta volver a ejecutarlo.
2. La ruta de las reglas se configura con `PLANTING_RULES_PATH` y la del CSV de estación con `STATION_CSV_PATH`. El archivo se lee en cada petición: no hace falta reiniciar.
3. Para activar la validación local, coloque el CSV real en `data/estaciones/camotan_insivumeh.csv` (columnas `fecha`, `precipitacion_mm`; mm/día). La interfaz **no** sube archivos.
4. Un archivo de reglas ausente o con JSON inválido solo desactiva estos endpoints (503 con motivo); el resto de la aplicación sigue funcionando.
5. Las reglas de este módulo no entran en el hash de las corridas del motor: cambiarlas no invalida corridas guardadas.

## 7. Pendientes de validación oficial y de campo
- **MAGA/ICTA:** confirmar ventanas de primera y postrera para Jocotán; ciclo y floración de ICTA B-9 y B-15; ciclos recomendados por variedad; Kc locales; umbrales hídricos con cita.
- **INSIVUMEH:** serie diaria 2001–2025 de la estación Camotán; procedimiento oficial del inicio de la época lluviosa.
- **Campo:** calibrar duraciones de etapas y Kc con observaciones locales.

## 8. Pruebas
`apps/api/tests/test_agronomy.py` (validación, ventanas y límites, umbrales, JSON ausente/mal formado/cambio sin tocar código, pentadas con huecos y años bisiestos, retraso, estación con CSV válido/incompleto/sucio, métricas exactas, ejemplo ficticio, mensajes es/en), `tests/integration/test_agronomy_api.py` (PostGIS real), `apps/web/src/components/zone/AgronomyValidation.test.tsx` y `tests/contract` (38 operaciones).
