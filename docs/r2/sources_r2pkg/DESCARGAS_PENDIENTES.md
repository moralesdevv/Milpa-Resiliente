# Guía de URLs para reunir los insumos pendientes de R2

Consulta: 2026-11-15. Este índice responde qué obtener, de dónde y qué queda
por validar. Los enlaces oficiales permiten descargar documentos/datos o
solicitar mediciones; las páginas web no reemplazan acuerdos con agricultores,
decisiones del equipo ni validación agronómica.

## Descargas públicas recomendadas

| Requisito del MVP | URL de descarga/portal | Qué guardar | Estado/uso |
|---|---|---|---|
| ET0 FAO-56, Kc y calendario fenológico base | [FAO-56 completo](https://www.fao.org/4/x0490e/x0490e00.htm) | Capítulos 3–4 y 6–8; tablas/casos usados con cita | Base metodológica internacional; valores deben contrastarse localmente |
| Fórmula y contexto de precipitación efectiva | [FAO Irrigation Water Needs, cap. 4](https://www.fao.org/4/S2022E/s2022e08.htm) | Método mensual ilustrativo y ejemplos | No usar automáticamente por decena; registrar como método y sensibilidad |
| Métodos empíricos de Pef, USDA-SCS | [FAO Effective Rainfall, cap. II](https://www.fao.org/4/X5560E/x5560e03.htm) | Descripción del método y límites de aplicación | Leer la sección USDA-SCS; el equipo debe decidir versión/fórmula y justificar escala |
| Pruebas de ET0 | [FAO ETo Calculator](https://www.fao.org/land-water/resources/tools/software/eto-calculator/en) | Manual/software público y ejemplos de control | Referencia de implementación; los casos de Paper 56 siguen siendo la autoridad |
| Maíz: variedades, zonas y guías de Oriente | [Publicaciones de Maíz ICTA](https://www.icta.gob.gt/publicacionesdemaiz) | Guía agronómica, recomendaciones de Oriente, B-7TS y B-5 | Descargar documentos pertinentes; extraer fuente, año, variedad, altitud, manejo |
| Guía de maíz para zona de humedad limitada | [Guía agronómica ICTA](https://www.icta.gob.gt/publicaciones/Maiz/Aspectos%20generales%20y%20guia%20para%20el%20manejo%20del%20maiz.pdf) | Ciclo/variedades y recomendaciones | Referencia de catálogo; no sustituye validación de variedad presente en el piloto |
| Maíz resistente a sequía B-7TS | [ICTA B-7TS, boletín](https://www.icta.gob.gt/publicaciones%202021/boletines/ICTA%20bolet%C3%ADn%20Enero%202021.pdf) | Días a floración/madurez, altitud recomendada, ventanas sugeridas | La fuente reporta 57 días a floración y 90 a madurez; fuente distinta de otras fichas, conservar ambos |
| Maíz específicamente Oriente | [Recomendaciones ICTA para Oriente](https://www.icta.gob.gt/publicaciones/Maiz/Recomendaciones%20tecnicas%20de%20maiz%20ICTA.pdf) | Adaptación regional y manejo B-7 | Útil para R1/R2; revisar año y representatividad |
| Frijol: variedad y fenología | [Publicaciones de Frijol ICTA](https://www.icta.gob.gt/publicacionesdefrijol.php) | Fichas/manuales de ICTA Ligero, Ostúa, Chortí, Petén, Sayaxché | Descargar la ficha de la variedad confirmada localmente |
| Calendario de frijol | [Manual ICTA de producción de frijol](https://www.icta.gob.gt/publicaciones/Frijol/Manual%20de%20producci%C3%B3n%20de%20frijol%20ICTA.pdf) | Primera/postrera y prácticas | Referencia nacional con variación por región |
| Frijol: datos de variedades | [Producción de frijol ICTA](https://www.icta.gob.gt/publicaciones/Frijol/Produccion%20de%20Frijol%20Phaseolus%20vulgaris%20L%202011.pdf) | Días a floración/cosecha, adaptación y rendimientos de referencia | No convertir rendimiento experimental en predicción del hogar |
| Ensayos en Corredor Seco | [Líneas tolerantes de frijol, ICTA/CRIA](https://www.icta.gob.gt/publicaciones/Informes%20Finales%20IICA-CRIA%202020/11%20FRIJOL%20ORIENTE/Lineas%20tolerantes%20mosaico-ICTA-J%20Saguil/Evaluaci%C3%B3n%20de%20lineas%20avanzadas%20de%20frijol.pdf) | Sitios, fechas y tratamientos de ensayo | Evidencia experimental localizada; no es calendario de cada comunidad |
| Ventanas sugeridas por riesgo climático | [Comunicado ZARC Guatemala](https://guatemala.gob.gt/presentan-resultados-y-aporte-a-la-agricultura-familiar-de-la-herramienta-zarc/) | Resultados publicados para Corredor Seco | Solicitar a MAGA/DIGEGR los archivos/metodología que originan resultados; comunicado no trae el dataset |
| Acceso a la herramienta ZARC | [Plantio Certo/ZARC](https://play.google.com/store/apps/details?id=embrapa.br.zonamento) | Aplicación y documentación enlazada | La aplicación descrita es de ZARC Brasil; no asumir que tiene calibración Guatemala |
| Pronósticos de inicio lluviosa | [INSIVUMEH: inicio 2026](https://insivumeh.gob.gt/conoce-cuando-sera-el-inicio-de-la-epoca-lluviosa-por-el-ano-2026/) | Boletines anuales como evidencia contextual | No descarga una definición fija de `t0`; definir regla reproducible con socio/equipo |
| Datos de estaciones históricos | [Climatología INSIVUMEH](https://insivumeh.gob.gt/4063-2/) | Solicitud de datos de estación, especialmente Camotán/Chiquimula | El portal indica contacto para solicitar series; el CSV web encontrado es corto/preliminar |
| CSV públicos recientes de estaciones | [Directorio INSIVUMEH CSV](https://insivumeh.gob.gt/img/Estaciones_Met/output_csv_estacion/) | CSV de Camotán y estaciones cercanas | El snapshot incluido solo tiene 32 días; consultar condiciones de redistribución |
| Comparación POWER con terreno | [NASA POWER Validate/PRUVE](https://power.larc.nasa.gov/docs/services/api/validate/) | Datos de validación disponibles y reporte por variable | Orienta comparación; no valida por sí sola el sitio de Camotán |
| Precipitación satelital | [NASA GPM Data Directory](https://gpm.nasa.gov/data/directory) | IMERG Final V07B; producto diario/medio horario y metadatos | Usar Final para investigación; guardar versión, unidad, escala, run, DOI y hash |
| IMERG guía y significado | [NASA IMERG](https://gpm.nasa.gov/data/imerg) | Manual y release notes enlazadas | Revisar unidades/runs antes de descargar |
| Suelo medido (pH, textura, MO) | [Laboratorio de suelos ICTA](https://www.icta.gob.gt/programasuelos) | Procedimiento, formulario y servicios de análisis | Solicitar muestras representativas en parcelas consentidas |
| Solicitud/envío de muestras | [Proceso laboratorio ICTA](https://www.icta.gob.gt/procesoslaboratoriosuelos.html) | Formulario, instrucciones y reporte de laboratorio | Confirmar precios, acreditación y métodos directamente con ICTA antes del muestreo |
| Mapa global de suelo | [SoilGrids](https://isric.org/explore/soilgrids/) | Capas pH, sand/silt/clay, SOC, BD y agua; cuantiles | CC-BY 4.0 según ISRIC; es estimación espacial, no medición parcelaria |
| SoilGrids variables/unidades | [SoilGrids FAQ](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html) | Unidades, profundidades estándar e incertidumbre | Necesario para conversión y PTF |
| PTF candidato | [Saxton & Rawls 2006 DOI](https://doi.org/10.2136/sssaj2005.0117) | Artículo y ecuaciones según acceso institucional | PTF candidato, no “aceptado” hasta revisión del asesor y contraste local |
| Elevación | [NASA SRTM](https://www.earthdata.nasa.gov/s3fs-public/2025-05/SRTM_Quick_Guide.pdf) | DEM 1 arc-second si cobertura/calidad adecuada | Descargar mosaico del área; registrar versión, vertical datum y vacíos |
| Escenarios climáticos posteriores | [NASA NEX-GDDP-CMIP6](https://www.nasa.gov/ames/earth-science/nasa-earth-exchange-nex/gddp/downscaled-climate-projections-nex-gddp-cmip6/) | Data/tech note si se decide usar proyecciones | Extensión futura; no reemplaza grilla sintética 27+18 del MVP |
| Precios para criterios económicos | [MAGA SIM: nacionales](https://precios.maga.gob.gt/nacionales/) | Serie histórica, boletín mensual/semanal y ficha de mercado | Elegir mercado/unidad/fecha; precio minorista no equivale al precio recibido por productor |
| Producción/rendimientos agregados | [MAGA informes de producción](https://precios.maga.gob.gt/smc/produccion/) | Informe de producción de granos básicos | Estadística nacional/departamental; solo referencia, verificar escala/manejo |
| Rendimientos y costos de referencia | [MAGA precios/fichas](https://precios.maga.gob.gt/otros/fichas-producto/) | Fichas, unidad y mercado | No sustituye costos variables locales; pedir registros de productor/cooperativa |
| Composición de alimentos | [INCAP: Tabla Centroamericana](https://bvssan.incap.int/publicacion-a-la-venta-006/) | Edición 2018 o revisión actual; energía y proteína por alimento | Publicación a la venta; verificar licencia y si se permite extracción/redistribución |
| CBA urbana/rural y hogar | [INE Canasta Básica Alimentaria](https://www.ine.gob.gt/canasta-basica-alimentaria/) | Excel/PDF 2024–2026, composición y metodología | La CBA describe patrón/costo; no usar como requerimiento nutricional individual sin norma |
| Microdatos de gasto/consumo | [INE ENCOVI 2023](https://www.ine.gob.gt/2024/08/21/el-ine-presenta-cifras-de-pobreza-en-guatemala/) | Bases, diccionario y guía de uso | Requiere descarga/registro según portal; no reemplaza datos consentidos del hogar piloto |

## Descargar datos web y guardar correctamente

Para cada activo descargado, conservar el original bajo `data/raw/`, registrar
la URL de origen, fecha de descarga, proveedor, versión, periodo, cobertura,
unidades, licencia y SHA-256 en `data/source_manifest.json`. No modificar el
original; la curación va en `data/curated/` y el paquete pequeño reproducible
en `data/demo/`.

## Requisitos que no se resuelven con una URL

Los siguientes puntos requieren decisiones, datos de campo o autorización:

1. Si el piloto cubre Jocotán, Camotán o ambos; límite generalizado y socio.
2. Cultivos/variedades que realmente siembra cada comunidad y estrategias
   multianuales; confirmarlos con productores/técnicos y registrar fecha,
   método de consulta y consentimiento.
3. Umbrales de estrés por cultivo × variedad × etapa × método Pef. FAO-56 da
   Kc y coeficientes hídricos generales, pero no provee automáticamente los
   umbrales críticos locales del documento.
4. Definición de `t0`, período seco posterior, retraso y adaptación; aprobarla
   con literatura citada y validación local antes de habilitar esos escenarios.
5. `phi`, método primario de Pef, tolerancias ET0 y cobertura/faltantes. Son
   decisiones de configuración con ADR y análisis de sensibilidad.
6. AWC/Dr0/profundidad efectiva medidos en parcelas. SoilGrids y PTF no
   convierten una predicción regional en medición de parcela.
7. Precios pagados al productor, costos de semilla/insumos/jornales y
   disponibilidades familiares. Los boletines públicos de mercado son
   referencias externas, no los datos declarados del hogar.
8. Consentimiento, textos de privacidad, licencias de redistribución y asesor
   agrónomo responsable.
9. `min_valid_years`, umbrales de estabilidad y cobertura común del ranking:
   deben aprobarse por el equipo según DP-08/DP-09.

## Nota sobre foros

Los foros, Reddit y testimonios pueden orientar a qué institución preguntar o
qué práctica investigar. No son fuentes aceptables para fijar Kc, umbrales,
PTF, inicio de lluvias, rendimientos de referencia o recomendaciones del
motor. Registrar una pista como `lead_unverified`, nunca como cita de catálogo.
