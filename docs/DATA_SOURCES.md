# Fuentes de datos (R1) — procedencia, licencia y estado

Resumen de las fuentes que usa `milpa_etl` (README §9). **Las licencias no están verificadas**: R1 deja `license` vacío y `redistributable = false` hasta leer los términos oficiales (DE-12 / DP-14). Citar cada fuente según su licencia antes de redistribuir.

| Código (`prov.data_source`) | Producto | Institución | NASA | Resolución | Estado | Uso en el MVP |
|---|---|---|---|---|---|---|
| `POWER_DAILY` (id 1) | NASA POWER diario, comunidad AG (T2M_MAX, T2M_MIN, T2MDEW, RH2M, WS2M, ALLSKY_SFC_SW_DWN, PRECTOTCORR) | NASA (MERRA-2, CERES) | sí | rejilla gruesa (~0,5° × 0,625°, **[Verificar]**) | implementado (`fetch power`) | clima base 2001-2025; lluvia de respaldo |
| `IMERG_FINAL_V07` (id 2) | GPM IMERG Final Run diario `GPM_3IMERGDF` V07 | NASA GES DISC | sí | 0,1° | implementado (`fetch imerg`, requiere `EARTHDATA_TOKEN` y autorizar GES DISC) | lluvia primaria 2021-01-01 a 2025-09-30 |
| `SOIL_CSV_FIXTURE` (id 3) | CSV sintético de suelo | datos sintéticos internos | no | — | solo fixtures | pruebas; **no** es un análisis real |
| DEM Copernicus 30 m | Copernicus GLO-30 | ESA / Copernicus | no | ~30 m | `data/dem/copernicus_glo30_jocotan.tif`; elevación del punto de referencia de Jocotán: 444.74 m. Media municipal: 894.05 m. Metadatos y hash en `regions/r2/copernicus_dem_jocotan.json`; la ingesta zonal `fetch dem` requiere `rasterio` y rol propietario para escribir en BD | elevación del punto de referencia; calcular media sobre la geometría de parcela para resultados parcelarios |
| SoilGrids 2.0 | ISRIC | ISRIC | no | 250 m | ETL municipal 3x3 en `tools/etl_soilgrids.py`; los resultados JSON se publican para el frontend. El REST está temporalmente pausado según ISRIC; la última ejecución no obtuvo datos | estimaciones a escala municipal, nunca análisis de laboratorio ni dato exacto de parcela |
| Estación local | CSV + `station.yaml` | — | no | — | **no implementado** (`validate --station-csv` existe en R1) | validación local; sin ella la evidencia de lluvia es C |

## Lo que R1 declara como limitación (README de R1, `curated_meta.json`)
- La lluvia es evidencia **C**: IMERG no está validado contra una estación de la zona; comparar IMERG con POWER **no** es validación.
- 81 % de los días de la serie 2001-2025 toman la lluvia de POWER (IMERG empieza en 2021); octubre-diciembre de 2025 también.
- POWER trae 9 días atípicos (≥ 100 mm con IMERG < 10 mm).
- Convención de día (UTC frente a UTC−6): sin resolver.
- Elevación y polígono de la zona piloto son **de prueba** (`zona_chiquimula_prueba.geojson`, `approximate: true`).

## Redistribución
`data/demo/` contiene solo datos **sintéticos rotulados** (`LEEME.txt`): sin coordenadas de parcelas ni datos personales. Los datos reales de NASA no se redistribuyen: se publican los scripts de descarga y el hash esperado.
