# Benchmarks T-B (BE-11)

Generado: 2026-11-15T07:25:56+00:00

## Condiciones

- **host**: Windows-11-10.0.26200-SP0
- **cpu_count**: 8
- **python**: 3.12.16
- **postgres**: 16.4 (Debian 16.4-1.pgdg110+2)
- **runs_base**: 30
- **parcels_per_user**: 5000
- **parquet_synthetic_rows**: 1000000
- **peak_rss_mb_process**: 0
- **transport**: ASGI en proceso (TestClient): NO incluye red ni uvicorn
- **db**: contenedor PostGIS local, misma máquina

## Resultados

| Prueba | Estado | n | min (ms) | p50 (ms) | p95 (ms) | máx (ms) | media (ms) | pico alloc Py (MB) | detalle |
|---|---|---|---|---|---|---|---|---|---|
| GET /healthz (ASGI en proceso, sin red) | medido | 120 | 26.417 | 32.895 | 52.808 | 61.664 | 35.487 | 0.19 |  |
| POST /v1/auth/login (Argon2id verify + JWT) | medido | 15 | 171.61 | 179.079 | 230.399 | 230.399 | 187.045 | 0.16 |  |
| GET /v1/parcels/{id} (JWT + RLS + generalización) | medido | 60 | 55.618 | 66.683 | 83.47 | 85.925 | 68.309 | 0.19 |  |
| GET /v1/zones (paginado) | medido | 60 | 45.221 | 72.0 | 96.336 | 111.789 | 72.585 | 0.18 |  |
| SQL: count(*) farm.parcel con RLS (10000 filas totales) | medido | 30 | 16.436 | 23.35 | 34.333 | 39.292 | 24.607 | 0.01 | detail={'filas_totales': 10000, 'filas_visibles': 5000} |
| Trabajo: crear + reclamar + ejecutar handler nulo + cerrar (en línea) | medido | 30 | 95.263 | 111.592 | 132.254 | 135.419 | 111.575 | 0.1 | detail={'nota': 'mide la sobrecarga del sistema de trabajos, no ciencia'} |
| Pool de procesos spawn: 12 trabajos parcel_delete (no-op), 1 worker(es) | medido | 1 |  |  |  |  |  |  | total_ms=5828.3; trabajos=12; workers=1; incluye_arranque_de_procesos_spawn=True |
| Pool de procesos spawn: 12 trabajos parcel_delete (no-op), 2 worker(es) | medido | 1 |  |  |  |  |  |  | total_ms=6611.2; trabajos=12; workers=2; incluye_arranque_de_procesos_spawn=True |
| Parquet: lectura completa (1,000,000 filas x 6 columnas) | medido | 7 | 122.668 | 169.695 | 235.86 | 235.86 | 170.004 | 30.14 | archivo_mb=30.1; escritura_ms=759.3 |
| Parquet: lectura de 2 columnas | medido | 7 | 67.578 | 74.032 | 114.008 | 114.008 | 82.031 | 12.58 |  |
| SHA-256 del archivo Parquet | medido | 7 | 165.627 | 189.714 | 215.879 | 215.879 | 186.421 | 2.11 | archivo_mb=30.1 |
| PDF: render Jinja2 + WeasyPrint | omitido |  |  |  |  |  |  |  | ReportRenderError: WeasyPrint/Pango no disponible en este host (ejecutar en la imagen Docker) |
| POST /v1/runs/{id}/rank (ranking + estabilidad) | bloqueado |  |  |  |  |  |  |  | Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa. |
| GET /v1/runs/{id}/heatmap | bloqueado |  |  |  |  |  |  |  | Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa. |
| GET /v1/runs/{id}/dekad-chart | bloqueado |  |  |  |  |  |  |  | Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa. |
| Corrida base (matriz estrategia x cohorte x fecha) | bloqueado |  |  |  |  |  |  |  | Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa. |
| Grilla de 45 corridas de escenarios | bloqueado |  |  |  |  |  |  |  | Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa. |

## Limitaciones

- Datos sintéticos de carga; no representan los volúmenes reales de MILPA.
- Mediciones en un host de desarrollo con otras cargas; no son objetivos de latencia ni capacidad de producción.
- El ranking, heatmap y matriz base dependen de R2 y no se miden.
- peak_py_alloc_mb solo cuenta asignaciones de Python (tracemalloc), no memoria nativa de pyarrow.

No se establece ningún objetivo de latencia a partir de estas cifras (spec R3 §23.2).
