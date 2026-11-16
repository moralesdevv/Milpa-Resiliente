# Fuentes web verificadas para R2

Fecha de consulta: 2026-11-15. Las URLs se registran para trazabilidad; una
fuente web no sustituye la validación local ni la firma de un asesor agrónomo.

## Metodología científica

| ID | Fuente | Uso R2 | Estado |
| --- | --- | --- | --- |
| SRC-FAO56 | [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm) | ET0 FAO-56 PM, fenología y requisitos de agua | Verificada |
| SRC-FAO56-KC | [FAO-56 capítulo Kc](https://www.fao.org/4/x0490e/x0490e0b.htm) | Kc inicial, medio y final; ajustes documentados | Verificada; valores locales pendientes |
| SRC-FAO-PEFF | [FAO effective rainfall](https://www.fao.org/4/X5560E/X5560E00.htm) | Conceptos y métodos de precipitación efectiva | Verificada; aplicación a decenas pendiente |
| SRC-ET0 | [FAO ETo Calculator](https://www.fao.org/land-water/resources/tools/software/eto-calculator/en) | Referencia de controles y datos faltantes | Verificada |

## Series y productos espaciales

| ID | Fuente | Uso R2 | Estado |
| --- | --- | --- | --- |
| SRC-POWER | [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | T2M, T2M_MAX, T2M_MIN, T2MDEW, RH2M, WS2M y radiación | Descargada para Camotán 2001–2025 |
| SRC-POWER-VALIDATE | [NASA POWER Validate API](https://power.larc.nasa.gov/docs/services/api/validate/) | Comparación contra observaciones terrestres | Disponible; validación pendiente |
| SRC-IMERG | [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Precipitación satelital | Documentación consultada; no sustituye validación local |
| SRC-IMERG-DIR | [IMERG Data Directory](https://gpm.nasa.gov/data/directory) | Versión, cobertura y resolución | V07B, cobertura global del producto desde 1998; 0.1° |
| SRC-IMERG-GIS-DAILY | [Final IMERG Daily GIS V07 DOI](https://arthurhou.pps.eosdis.nasa.gov/Documents/V07/doi/3IMERGHH_GIS_1DAY_V07.html) | Producto 3IMERGHH_GIS_1DAY, V07B, GeoTIFF/WorldFile, acumulación diaria | 9,039 días descargados, 2001-01-01–2025-09-30; faltan carpetas PPS de oct–dic 2025 |
| SRC-IMERG-GIS-README | [NASA IMERG GIS README](https://pps.gsfc.nasa.gov/Documents/README.GIS.pdf) | Escala, unidades, missing, nombres GIS y descarga | PDF oficial guardado en `data/raw/imerg/docs/`; manifiesto SHA-256 por archivo |
| SRC-SOILGRIDS | [ISRIC SoilGrids](https://isric.org/explore/soilgrids/) | pH, textura, carbono, agua y profundidad | Fuente identificada; extracción de zona pendiente |
| SRC-SOILGRIDS-DOC | [SoilGrids layers](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html) | Unidades, seis intervalos de profundidad e incertidumbre | Verificada |
| SRC-SRTM | [NASA SRTM Quick Guide](https://www.earthdata.nasa.gov/s3fs-public/2025-05/SRTM_Quick_Guide.pdf) | Elevación para presión atmosférica y DEM | Fuente identificada; raster pendiente |
| SRC-NEX | [NASA NEX-GDDP-CMIP6](https://www.nasa.gov/ames/earth-science/nasa-earth-exchange-nex/gddp/downscaled-climate-projections-nex-gddp-cmip6/) | Extensión de escenarios climáticos | Fuente identificada; no necesaria para el simulador 27+18 inicial |

## Guatemala y Corredor Seco

| ID | Fuente | Uso R2 | Estado |
| --- | --- | --- | --- |
| SRC-ICTA | [ICTA granos básicos](https://www.icta.gob.gt/publicacionesgranosbasicos) | Variedades y manuales de maíz, frijol y sorgo | Verificada |
| SRC-ICTA-FRIJOL | [Manual ICTA de frijol](https://www.icta.gob.gt/publicaciones/Frijol/Manual%20de%20producci%C3%B3n%20de%20frijol%20ICTA.pdf) | Ventana de primera y postrera | Verificada; validación local pendiente |
| SRC-ICTA-FRIJOL-DATOS | [Características de variedades ICTA](https://www.icta.gob.gt/publicaciones/Frijol/Produccion%20de%20Frijol%20Phaseolus%20vulgaris%20L%202011.pdf) | Días a floración, cosecha y adaptación | Verificada para frijol |
| SRC-ICTA-MAIZ | [Guía agronómica de maíz ICTA](https://www.icta.gob.gt/publicaciones/Maiz/Aspectos%20generales%20y%20guia%20para%20el%20manejo%20del%20maiz.pdf) | Variedades para humedad limitada; ciclo de ICTA B-7 | Verificada |
| SRC-ICTA-MAIZ-CHIQ | [Memoria ICTA 2002](https://www.icta.gob.gt/publicaciones/Memoriasicta/Memoria%20de%20labores%202002.pdf) | Floración, cosecha y resultados de B-7/B-5 en localidades, incluida Chiquimula | Verificada como ensayo histórico |
| SRC-ZARC-GT | [Gobierno de Guatemala: resultados ZARC](https://guatemala.gob.gt/presentan-resultados-y-aporte-a-la-agricultura-familiar-de-la-herramienta-zarc/) | Evidencia de ajuste mayo→junio y municipios incluidos | Verificada; resultado de ZARC, no regla universal del MVP |
| SRC-ZARC-FAO | [FAO Guatemala y ZARC](https://www.fao.org/guatemala/detalle/noticias/detail/la-fao-junto-a-los-gobiernos-de-guatemala-y-brasil-fortalecen-la-agricultura-familiar-con-herramientas-de-innovaci%C3%B3n-y-la-cooperaci%C3%B3n/es) | Parcelas experimentales en municipios de Chiquimula y otros departamentos | Verificada |
| SRC-INSIVUMEH-ONSET | [INSIVUMEH inicio de época lluviosa 2026](https://insivumeh.gob.gt/conoce-cuando-sera-el-inicio-de-la-epoca-lluviosa-por-el-ano-2026/) | Perspectiva anual y variabilidad regional de onset/canícula | Verificada; no proporciona una regla estable t0 para el motor |
| SRC-FAO-PEFF-CH4 | [FAO effective rainfall: empirical methods](https://www.fao.org/4/X5560E/x5560e03.htm) | Describe métodos empíricos y USDA-SCS | Verificada; fórmula que se adopte requiere ADR/cita |
| SRC-FAO-IRRIGATION | [FAO irrigation water needs](https://www.fao.org/4/S2022E/s2022e08.htm) | Ejemplos de lluvia efectiva mensual | Verificada |
| SRC-SAXTON-RAWLS | [Saxton & Rawls 2006, DOI 10.2136/sssaj2005.0117](https://doi.org/10.2136/sssaj2005.0117) | Posible función de pedotransferencia desde textura y materia orgánica | Referencia hallada; aceptación local/asesor pendiente |
| SRC-INSIVUMEH | [Climatología INSIVUMEH](https://insivumeh.gob.gt/4063-2/) | Estaciones, variables y solicitud de datos | Verificada |
| SRC-INSIVUMEH-CSV | [CSV públicos de estaciones](https://insivumeh.gob.gt/img/Estaciones_Met/output_csv_estacion/) | Muestra de estación Camotán | Descargada; solo 32 días |
| SRC-MAGA | [MAGA precios nacionales](https://precios.maga.gob.gt/nacionales/) | Precios, series y fichas de producto | Fuente identificada; serie para piloto pendiente |
| SRC-MAGA-FICHAS | [MAGA fichas de producto](https://precios.maga.gob.gt/otros/fichas-producto/) | Unidad y descripción de productos | Verificada |
| SRC-INCAP | [Tabla de composición de alimentos de Centroamérica](https://bvssan.incap.int/publicacion-a-la-venta-006/) | Calorías, proteína y composición | Fuente identificada; licencia/datos completos pendientes |
| SRC-INCAP-EJEMPLO | [Ejemplo de tabla condensada INCAP](https://bvssan.incap.int/local/E/E-670.pdf) | Formato de kcal y proteína | Verificada |
| SRC-CAMOTAN | [PDM/POT Camotán](https://sistemas.segeplan.gob.gt/share/SCHE%24SINIP/OTROS_DOCUMENTOS/318373-TRBAHVPCYS.pdf) | Coordenadas y elevación de cabecera | Verificada como referencia geográfica |
| SRC-JOCOTAN | [PDM/POT Jocotán](https://portal.segeplan.gob.gt/segeplan/wp-content/uploads/2022/08/2004_PDM_OT_Jocotan.pdf) | Coordenadas y contexto del municipio | Verificada como referencia geográfica |

## Licencias y precauciones

- SoilGrids declara CC-BY 4.0 en su página de producto.
- Para FAO, ICTA, INSIVUMEH, MAGA e INCAP se conserva el enlace y la
  atribución institucional; la redistribución de PDFs completos debe revisarse
  antes de publicarlos.
- Las coordenadas municipales son referencias públicas y no representan la
  geometría de parcelas. No se guardan coordenadas de productores.
