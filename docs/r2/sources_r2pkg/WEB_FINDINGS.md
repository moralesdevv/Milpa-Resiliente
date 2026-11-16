# Resultado de búsqueda web y brechas restantes

## Ya encontrado y agregado

1. Fuente FAO-56 para ET0, Kc y requerimientos de agua.
2. Documentación NASA POWER y una serie diaria JSON de Camotán de 2001–2025.
3. Documentación IMERG V07B, incluyendo cobertura 1998–presente y resolución
   nominal de 0.1°.
4. Documentación SoilGrids: propiedades, unidades, intervalos 0–5, 5–15,
   15–30, 30–60, 60–100 y 100–200 cm, además de cuantiles de incertidumbre.
5. Fuente SRTM para elevación.
6. Fuente NEX-GDDP-CMIP6 para escenarios climáticos posteriores.
7. Publicaciones ICTA sobre variedades y calendario de frijol.
8. Información pública de INSIVUMEH y un CSV actual de la estación Camotán.
9. Fuentes MAGA para precios, fichas y series históricas.
10. Fuente INCAP para composición alimentaria.
11. Coordenadas y elevación de referencia de Camotán y Jocotán.
12. Fuentes ICTA sobre maíz de humedad limitada y variedades ICTA B-7/B-5.
13. Evidencia pública de ZARC en municipios del Corredor Seco, incluidos
    Jocotán y Chiquimula; el comunicado reporta ajuste de siembra de mayo a
    junio, que no debe universalizarse sin validar cultivo/año/zona.
14. Perspectiva anual de INSIVUMEH para inicio de época lluviosa; confirma que
    el onset es regional y variable, pero no entrega una definición fija
    reproducible de `t0` para todos los años.
15. Referencia primaria de Saxton y Rawls (2006) para estimación de propiedades
    hidráulicas desde textura y materia orgánica. La elección de PTF continúa
    pendiente de asesoría y validación con muestras locales.
16. Ficha específica Final IMERG Daily GIS V07 y manual GIS NASA descargado.
    Confirma DOI 10.25966/564j-4331, acumulación 24h, 0.1°, TIFF/WorldFile y
    codificación. Se descargaron 9,039 pares TIFF/WorldFile V07B, del
    2001-01-01 al 2025-09-30; no hay carpetas PPS del 2025-10-01 al 2025-12-31.
    La autenticación PPS funcionó con una cuenta ya registrada.

## No resuelto por internet y debes buscarlo localmente o solicitarlo

- Decisión formal de si el piloto será Jocotán, Camotán o ambos.
- Polígono generalizado del área piloto y consentimiento del socio local.
- Estrategias reales de productores, variedades realmente utilizadas y
  calendario agrícola validado en campo.
- Umbrales de estrés por cultivo, etapa y método de Pef con cita específica.
- Parámetro `phi` de `fixed_fraction` y elección del método primario de Pef.
- Definición citada de inicio de lluvias (`t0`) y regla de adaptación.
- Mediciones de suelo locales: AWC, profundidad efectiva, textura, materia
  orgánica, pH, profundidad radicular y `Dr0`.
- Función de pedotransferencia aceptada por el asesor agrónomo.
- Precios y costos representativos del mercado del piloto, con fecha, unidad y
  fuente; los boletines MAGA encontrados no sustituyen esa selección.
- Tamaño de hogar y requerimientos alimentarios declarados.
- Licencia y permiso de redistribución de los documentos/datos no abiertos.
- Tolerancias numéricas oficiales para las pruebas FAO-56.
- Parámetros de faltantes, mínimos de años, umbrales de estabilidad y
  cobertura mínima de criterios.
- Validación cruzada IMERG/POWER/INSIVUMEH en la zona.
- Definición algorítmica multianual de `t0`: los boletines de inicio de lluvias
  son pronósticos/perspectivas anuales, no sustituyen la regla agroclimática
  reproducible pedida por el diseño.
- Confirmación de que ICTA B-7/B-5 y ICTA Ligero son variedades realmente
  utilizadas por las comunidades piloto y en qué altitudes/manejos.
- Datos IMERG GIS para el último trimestre de 2025: las carpetas no estaban
  disponibles en el archivo PPS consultado. Se guardó el intervalo publicado;
  confirmar con PPS cuándo se reprocesará/publicará el tramo faltante.

## Evidencia de calendarios y variedades encontrada

- El manual ICTA de frijol describe primera normalmente entre 15 de mayo y
  15 de junio y postrera en septiembre/octubre, con variación entre zonas.
- Un ensayo ICTA de frijol en San Juan Ermita, Chiquimula, ubicó una siembra de
  postrera el 4 de septiembre de 2016; es un ensayo, no un calendario oficial
  para todas las aldeas.
- Una memoria ICTA registra para ICTA B-7 aproximadamente 53 días a floración,
  110 días a cosecha y siembras de primera mayo-junio y segunda septiembre.
- ICTA describe B-7 como material recomendado para zona de humedad limitada,
  ciclo de 95 días en su guía de maíz. La diferencia entre publicaciones
  demuestra que el dato depende de fuente, ensayo, manejo y definición de
  madurez; no se deben mezclar en un catálogo congelado sin revisión técnica.
- El Gobierno de Guatemala reporta resultados ZARC que sugieren mover siembra
  de mayo a junio en determinadas áreas del Corredor Seco. Es evidencia de
  análisis territorial, no una fecha prescriptiva general.

## Foros y testimonios

Se encontró una conversación en Reddit donde un participante relata siembra
tradicional en mayo y cosechas posteriores. Se conserva solo como pista
cualitativa; no se usa para parámetros, fechas ni validación científica.

## Limitación de los datos descargados

`data/raw/imerg/daily_tif/` contiene 9,039 GeoTIFF diarios y 9,039 WorldFiles
del producto Final V07B, 2001-01-01–2025-09-30, sin faltantes internos.
El archivo PPS no ofrecía las fechas 2025-10-01–2025-12-31 al momento de la
consulta. La serie municipal derivada está en `data/curated/imerg/`; Camotán y
Jocotán caen en la misma celda de 0.1°, así que esa extracción no es una
comparación independiente entre municipios ni una validación de estaciones.

`data/raw/insivumeh/camotan_public_snapshot.csv` contiene 32 filas públicas,
del 2026-05-16 al 2026-06-16. No es una serie de 25 años.

`data/raw/power/camotan_power_2001_2025.json` contiene 9,131 fechas diarias,
del 2001-01-01 al 2025-12-31. Es una respuesta de NASA POWER para el punto de
referencia municipal, no una medición de parcela ni una serie curada.

Por tanto, ambos archivos son insumos de investigación y no deben presentarse
como datos validados del piloto hasta completar QC, metadatos, comparación con
estaciones y aprobación de R1.
