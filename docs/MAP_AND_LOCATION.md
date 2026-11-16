# Mapa y selección de ubicación

Decisión: [ADR-022](decisions/ADR-022-limite-municipal-y-seleccion-de-ubicacion.md). Estado: **propuesto**.

## Límite municipal
| Campo | Valor (salida de `python -m api.cli check-boundary`) |
|---|---|
| Archivo | `regions/jocotan_chiquimula_boundary.geojson` |
| Municipio / departamento | Jocotán / Chiquimula |
| `COD_MUN` / `COD_DEPTO` | 2004 / 20 |
| CRS | EPSG:4326 (validado) |
| Vértices | 320 |
| BBox (lon, lat) | −89.5020, 14.7222 → −89.2136, 14.9060 |
| SHA-256 | `07222a540e3f2cb87f844feb31b8f64260df08de8f8ebd602a55f8c482192be2` |
| Fuente declarada | **no declarada en el archivo** |

**Procedencia pendiente de confirmar por quien aportó el archivo.** No se asume ninguna institución (SEGEPLAN, IGN u otra): hasta confirmarlo, el informe y la interfaz no deben atribuirla.

## Cómo se aplica
- Servidor (autoritativo): con `MUNICIPAL_BOUNDARY_FILE` definido, `POST /v1/parcels` responde 422 si la ubicación queda fuera del municipio (`ST_Covers` en PostGIS) sin repetir la coordenada; si el archivo es inutilizable responde 503 (falla cerrado). Vacío = solo la regla de zona.
- Navegador: `apps/web/src/lib/boundary.ts` repite la comprobación punto-en-polígono (inclusivo en el borde) con el mismo GeoJSON, solo como ayuda visual.
- La demo pública **no crea parcelas** (`security/demo.py`); el mapa no guarda ni envía la coordenada.

## Teselas del mapa
OpenStreetMap con atribución visible, uso ligero. Para otro proveedor permitido: `VITE_MAP_TILE_URL` y `VITE_MAP_ATTRIBUTION` (sin token en el repositorio). Si las teselas fallan, el mapa muestra un aviso y conserva el límite y las capas.

## Capas
Límite municipal · celdas climáticas (capa de **contexto**) · zona de análisis · selección. Hoy solo la celda **POWER** de `camotan_jocotan` está registrada en `geo.climate_cell`; la celda IMERG 0,1° coincide con el polígono de la zona y se dibuja como «zona de análisis» (pendiente decidir si se registra como celda).

## Lo que no existe a propósito
Buscador de localidades: no hay una fuente fiable de licencia clara y Nominatim restringe el autocompletado. La alternativa accesible al clic es el formulario de coordenadas del mapa.
