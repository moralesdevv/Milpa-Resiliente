# ADR-004: Integración PostGIS y generalización geográfica

- **Fecha:** 2026-11-14 · **Estado:** aceptado (PostGIS); **propuesto** (método de generalización, DP-13)

## Contexto y problema
PostGIS se usa para zonas, pertenencia de un punto a una zona y generalización de la ubicación de parcelas. La rejilla de generalización debe ser **≥ 1 km** reales y el punto original no se persiste ni se registra (README §22).

## Alternativas
- GeoJSON en `jsonb` + `shapely` (respaldo del README): rechazado mientras el equipo mantenga PostGIS.
- Rejilla en grados: no corresponde a metros.
- `ST_SnapToGrid` en EPSG:3857: 1000 «m» de Mercator son ~970 m reales a 14° N → **incumpliría el mínimo**.
- **Proyección UTM de la zona del punto + `ST_SnapToGrid` + centro de celda (elegida).**

## Decisión
`ParcelRepository.generalize()` calcula en una sola consulta SQL: UTM (`326xx/327xx`), celda `floor(x/G)·G + G/2` con `ST_SnapToGrid`, vuelta a 4326. `display_grid_m ≥ 1000` (CHECK en BD y validación en `Settings`). El punto original solo viaja como parámetro de esa consulta. Además se exige `ST_Covers(zona, punto)` (si no, 422 sin repetir coordenadas). La API devuelve el centro redondeado a 3 decimales.

## Consecuencias / riesgos
(+) Verificado en pruebas (`test_generalized_point_is_snapped_to_utm_grid_of_at_least_1km`). (−) Celdas partidas en los límites de huso UTM; aceptable para ≥ 1 km. El valor definitivo de G sigue en DP-13 (provisional 1000 m).

**Aprobadores:** R3 + revisión legal/operativa (DP-13).
