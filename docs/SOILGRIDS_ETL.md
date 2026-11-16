# ETL de SoilGrids para Jocotán

## Archivos

- Polígono: `data/regions/jocotan.geojson` (EPSG:4326).
- DEM Copernicus GLO-30: `data/dem/copernicus_glo30_jocotan.tif`.
- Archivo original del DEM: `data/dem/copernicus_glo30_jocotan.tar.gz`.
- Script: `tools/etl_soilgrids.py`.
- Resultados para análisis: `data/soilgrids/`.
- Copia JSON servida por la aplicación web: `apps/web/public/data/soilgrids/jocotan_promedio.json`.

## Instalación y ejecución

Desde la raíz del repositorio, con Python 3.12:

```powershell
uv run --project packages/milpa_etl --extra soilgrids python tools/etl_soilgrids.py
```

Si se usa `pip` en el entorno virtual del proyecto:

```powershell
python -m pip install geopandas shapely requests pandas numpy
python tools/etl_soilgrids.py
```

El script consulta una vez por punto y solicita las seis propiedades en cada llamada. Aplica una
pausa mínima de 1.2 segundos y además limita el ritmo a cinco llamadas por minuto, según la política
de uso publicada por ISRIC.

## Resultados

- `data/soilgrids/jocotan_puntos_detalle.csv`: coordenadas, estado y estimaciones convertidas.
- `data/soilgrids/jocotan_promedio.json`: promedios por propiedad, unidades y estado del ETL.
- `data/soilgrids/manifest.json`: fecha, fuente, GeoJSON, profundidad, puntos y errores.

El JSON de promedio se copia también a `apps/web/public/data/soilgrids/` para que la pantalla Mi
zona lo consuma. Tras ejecutar de nuevo el ETL, reconstruye el frontend para incluir la actualización
en `dist`.

SoilGrids produce estimaciones modeladas a unos 250 m, no resultados de laboratorio ni valores
representativos de una parcela por sí solos. ISRIC informa que el servicio REST v2.0 está
temporalmente pausado; cuando falle, el script deja los resultados en estado `unavailable` y no
inventa valores. Consulta la [documentación de acceso de SoilGrids](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_02.html)
antes de volver a ejecutar la ingesta.
