# ADR-022: Límite municipal y selección de ubicación

- **Fecha:** 2026-11-16 · **Estado:** **propuesto**
- **Contexto:** el mapa del frontend permite elegir un punto y `POST /v1/parcels` solo exigía que cayera dentro de la zona. Se necesita impedir ubicaciones fuera de Jocotán sin persistir coordenadas precisas.

## Decisión
1. Límite oficial como archivo GeoJSON versionado (`regions/jocotan_chiquimula_boundary.geojson`). `api.geo.boundary` lo valida (1 municipio, EPSG:4326, anillos cerrados, dentro de Guatemala, sin autointersección) y calcula SHA-256; `python -m api.cli check-boundary` lo imprime.
2. `Settings.municipal_boundary_file` (variable `MUNICIPAL_BOUNDARY_FILE`; vacío = sin regla). Con ruta, `POST /v1/parcels` rechaza (422, sin repetir la coordenada) lo que quede fuera con `ST_Covers` en PostGIS; un archivo inutilizable devuelve 503 (**falla cerrado**).
3. El frontend empaqueta el mismo GeoJSON (`lib/boundary.ts`) para comprobar al clic; **la validación autoritativa es la del servidor**.
4. La demo pública no crea parcelas (`security/demo.py`): el mapa es solo comprobación visual y no guarda nada.
5. No hay buscador de localidades: no existe fuente fiable de licencia clara y Nominatim restringe el autocompletado.

## Consecuencias / riesgos
- **La procedencia/atribución del polígono no consta en el archivo**: debe confirmarla quien lo proporcionó (no se asume SEGEPLAN ni IGN).
- Teselas OSM con atribución y uso ligero; configurables con `VITE_MAP_TILE_URL` / `VITE_MAP_ATTRIBUTION`.
- Solo se cubre un municipio; ampliar exige otro archivo y revisar la regla de zona.

**Módulos:** `geo/boundary.py`, `config/settings.py`, `repositories/farms.py`, `services/parcels.py`, `apps/web/src/lib/boundary.ts`, `components/zone/ZoneMap.tsx`. **Aprobadores:** R3, R4.
