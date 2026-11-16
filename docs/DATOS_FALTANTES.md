# Datos que faltan para completar la demo (2026-11-16)

Lo que la página muestra hoy como «No disponible», «Pendiente de validación» o «No evaluable», dónde se ve, qué
habría que conseguir y de dónde. **Nada de esto se inventa**: mientras falte, la página lo dice (regla P9).

> **Actualización 2026-11-16 (validación agronómica):** ya se investigaron ciclos/floración/Kc de ICTA B-7, B-5, Ostúa y Santa Gertrudis (ver `docs/VALIDACION_AGRONOMICA_JOCOTAN.md`). Siguen **sin dato**: ciclo y floración de **ICTA B-9 e ICTA B-15**, Kc medidos por variedad (se usan proxies FAO-56), ventanas oficiales de Jocotán, umbrales hídricos con cita y la serie de la estación Camotán (INSIVUMEH).

## A. Prioridad alta — desbloquean resultados que hoy no existen
| # | Dato | Dónde se nota hoy | Qué buscar / fuente sugerida | Dónde se carga |
|---|---|---|---|---|
| 1 | **Kc y duración de etapas por cultivo/variedad** (16 de 16 etapas sin cita) | «Pending decisions» en Mi zona/MVP; todo el resultado es «provisional» | FAO-56 tablas 11–12 (https://www.fao.org/4/x0490e/x0490e0b.htm); fichas ICTA (maíz ICTA B-7/B-5, frijol ICTA Ostúa/Santa Gertrudis) | `catalogs/r2/crops.yaml` (poner `citation`) |
| 2 | **Umbrales de exposición hídrica en etapas críticas** (3 de 3 sin cita) | «Provisional threshold — do not use for decisions» en cada cifra | Literatura de estrés hídrico en floración/llenado de grano de maíz y frijol; asesor agrónomo MAGA/ICTA | `catalogs/r2/thresholds.yaml` |
| 3 | **Ventanas de siembra y año agrícola oficiales** (hoy valores de prueba: primera 05-01→06-30, postrera 08-20→09-30) | Mi zona → cultivos «Pending validation» | MAGA «Épocas de siembra y cosecha» (https://www.maga.gob.gt/download/epocas-siembra-cosecha-agricolas-guatemala.pdf), SCEP-MAGA Jocotán (https://scep.gob.gt/wp-content/uploads/2023/11/Jocotan.pdf), boletín agroclimático Chiquimula | `regions/r2/pilot_corredor_seco.yaml` |
| 4 | **Definición de inicio de lluvias y retraso de adaptación** (sin cita) | Escenarios de retraso «sandbox only» | INSIVUMEH / literatura del Corredor Seco | mismo YAML (`onset`, `adaptation`) |
| 5 | **Validación de lluvia con estación local** (hoy evidencia C) | «Rainfall evidence is level C» | Datos diarios de una estación INSIVUMEH cercana (Camotán/Jocotán/Chiquimula), 2001–2025 | cargar en R1 y comparar con IMERG |

## B. Para activar criterios que hoy están «No evaluables»
| # | Dato | Efecto | Fuente sugerida |
|---|---|---|---|
| 6 | **Rendimientos de referencia, precios y costos variables** (maíz blanco, frijol negro, sorgo) | Criterios *alimentación* e *ingresos* excluidos del ranking | MAGA (precios), SIPA/MAGA, ENCOVI/INE; fecha y fuente obligatorias | `catalogs/r2/reference/economics.yaml` / `ph_tolerance.yaml` |
| 7 | **Composición de alimentos** (kcal, proteína por kg) | Criterio alimentación | Tabla de composición de alimentos de INCAP | `catalogs/r2/ph_tolerance.yaml` (`food_composition`) |
| 8 | **Profundidad radicular y fracción de agotamiento (p) con cita** por variedad | Modo B (balance del suelo) no corre: «cited root depth…» | FAO-56 tabla 22 y 12 | `catalogs/r2/crops.yaml` |
| 9 | **Capacidad de agua disponible (AWC), profundidad efectiva y condición inicial del suelo** | «Exposure is not soil water» | Análisis de suelo de parcela o mapa edafológico (MAGA/IGN); SoilGrids da solo textura | carga de suelo por parcela |
| 10 | **Matriz de tolerancia de pH por cultivo** | Valor de la información del suelo (VoI) no disponible | Fichas de cultivo ICTA / FAO | `catalogs/r2/ph_tolerance.yaml` |
| 11 | **Fijación de N del frijol (condiciones)** | Subindicador de suelo condicionado | Literatura de nodulación en frijol común | `catalogs/r2/crops.yaml` |

## C. Datos de origen / metadatos que faltan (la página los muestra vacíos)
| # | Dato | Dónde se ve |
|---|---|---|
| 12 | **Versión de NASA POWER** (el manifiesto dice v2.10.3 pero `prov.data_source.version` está vacío) | Tabla «Data sources», columna Version = «Not available» |
| 13 | **Cita formal de POWER e IMERG** (`citation_id` vacío) | Tabla de fuentes; informe |
| 14 | **Autoría/fuente del polígono municipal de Jocotán** (el archivo no la declara) | `docs/MAP_AND_LOCATION.md`; confirmar con quien lo aportó (SEGEPLAN/IGN u otra) |
| 15 | **IMERG de oct–dic 2025** (la serie IMERG termina el 2025-09-30; POWER rellena) | Cobertura 2025: 25,2 % sin dato IMERG |
| 16 | **Celda IMERG registrada en `geo.climate_cell`** (hoy solo la celda POWER) | Mapa: la celda IMERG se dibuja como «zona de análisis» |
| 17 | **Nombre legible de la zona** («Corredor Seco — Jocotán, Chiquimula») en vez de `camotan_jocotan` | Selector de zona, informe |
| 18 | **Elevación para el ET0**: la región usa 444,74 m (punto de referencia) mientras la media zonal del DEM es 816 m y la rejilla POWER 762 m | Decisión científica pendiente (afecta el ET0) |

## D. Fuentes NASA/otras contempladas y aún no integradas (se muestran como «Not integrated»)
SMAP (humedad del suelo), MODIS/HLS/Landsat 8-9 (vegetación), NEX-GDDP-CMIP6 (proyecciones), Sentinel-1/2, INAB/MAGA/SEGEPLAN como
conjuntos versionados. Para el jurado basta con declararlas como alcance futuro; integrarlas exige un conector ETL con procedencia.

## Lo que sí está con datos reales
NASA POWER diario 2001–2025 (zona camotan_jocotan), GPM IMERG Final V07B 2001-01-01→2025-09-30, DEM Copernicus GLO-30
(elevación media 816 m, pendiente 39 %), SoilGrids 250 m (media de 3 puntos, 0–5 cm), límite municipal de Jocotán.
