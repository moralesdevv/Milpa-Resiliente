# R2 — Motor científico (`milpa_core`) · guía rápida

Paquete listo para copiar al monorepo. Implementa SE-01 a SE-11 (Modo B básico) y la base de SE-12/SE-13.
**58 pruebas verdes** (FAO-56 ej. 8 y 18, T-P01…T-P17, T-G03/T-G04, integración).
Todo corre en **sandbox**: catálogos y umbrales sin cita → cada resultado sale `provisional`, evidencia C.

## 1. Copiar al monorepo (2 min)

```
packages/milpa_core/        → packages/milpa_core/        (núcleo, sin E/S)
tools/milpa_adapter.py      → apps/api/src/api/services/ (o déjalo en tools/): lee YAML + daily.parquet
tools/r2_run.py             → CLI de corrida (make run-base / scenarios / examples)
tools/make_synthetic.py     → serie sintética rotulada para pruebas sin R1
regions/*.yaml, catalogs/*  → fusionar con los de R1 (R1 es dueño de catalogs/)
docs/METHODS.md             → docs/METHODS.md
Makefile.r2                 → pegar los objetivos en el Makefile
examples/                   → payloads JSON de ejemplo para R3 y R4
```

## 2. Correr (1 min)

```bash
pip install numpy pandas pyyaml pyarrow pytest      # pyarrow para leer el Parquet de R1
make -f Makefile.r2 test-science                    # 58 pruebas
python tools/r2_run.py --daily data/curated/chiquimula_prueba/daily.parquet --out data/results/base
python tools/r2_run.py --daily data/curated/chiquimula_prueba/daily.parquet --grid --out data/results/grid
```

Antes de la primera corrida con datos reales, ajusta en `regions/pilot_corredor_seco.yaml`:
`zone.elevation_m` (elevación media del DEM de R1), `zone.cell_id` si hay varias celdas, y la ventana
2021–2025. El resumen imprime `et0_parity_vs_R1` (diferencia media entre la ET0 de R1 y la del motor).

**Contrato con R1** (columnas de `curated/<zona>/daily.parquet`): `cell_id, obs_date, tmax_c, tmin_c,
tdew_c, rh_pct, wind2m_ms, srad_mj_m2, precip_mm, qc_flags` (+ `et0_mm` opcional para paridad).
Días ausentes se reindexan como NaN; la lluvia nunca se rellena.

## 3. Qué recibe R3 (fachada estable)

```python
from milpa_core import make_context, run_analysis, rank, rank_stability, soil_voi, run_grid, standard_grid, BASE
ctx  = make_context(region, catalogs, series, strategies, soil)          # valida estrategias, ET0 y Pef
run  = run_analysis(ctx, BASE, AdaptationMode.NONE)                       # → ScenarioRunResult
r, x = rank(ctx, run, weights)                                            # soporte común + decision_log
st   = rank_stability(r, StabilityConfig())                               # 4 estados + conflictos
voi  = soil_voi(ctx, run, r, weights)                                     # pH
```
Payloads con forma de DTO (todo número en `Indicator` con procedencia): `milpa_core.dto`
(`run_summary_dto`, `rank_response_dto`), `planting.heatmap_cycle/heatmap_strategy`,
`exposure.dekad_chart`, `report_model.build_report`. Ejemplos en `examples/*.json`.
Errores tipados con `code` RFC 7807 en `milpa_core.errors`. Enums: `examples/enums.sql` y `enums.json`
(paridad Python ↔ SQL ↔ OpenAPI).

| Archivo de ejemplo | Endpoint de R3 |
|---|---|
| `summary.json` | `GET /v1/runs/{id}/summary` (StrategyRiskDTO + CycleRiskDTO) |
| `heatmap.json` | `GET /v1/runs/{id}/heatmap?view=cycle` o `view=strategy` |
| `dekad_chart.json` | `GET /v1/runs/{id}/dekad-chart` |
| `rank.json` | `POST /v1/runs/{id}/rank` (RankResponse con estabilidad) |
| `soil_voi.json` | `POST /v1/runs/{id}/soil-voi` |
| `scenarios.json` | `GET /v1/runs/{id}/scenarios` (45 corridas × 2 lecturas) |
| `report_model.json` | entrada de la plantilla del informe (`POST /v1/reports`) |
| `results/<run_id>/BASE/none/cycle_result.*` | Parquet de resultados por ciclo |

## 4. Rendimiento medido (serie sintética, 7 estrategias, 5 años)
Corrida base 0.3 s · grilla completa (45 escenarios × 2 lecturas = 90 corridas) ≈ 14 s en un núcleo.

## 5. Lo que falta / decisiones que debes confirmar
1. **Umbrales**: los de `catalogs/thresholds.yaml` están calibrados para que la demo discrimine en la
   serie sintética. Con la serie real de R1 revísalos; no tienen significado agronómico.
2. **Kc y etapas**: valores candidatos de FAO-56 (Tablas 11, 12, 22) con `citation: null` → verificar
   con el asesor (DE-08) y poner la cita para que dejen de ser provisionales.
3. Reglas **[Propuesto R2]** en `docs/METHODS.md` (agua = 1 − proporción crítica, severidad de la
   asociación = máximo de componentes, fecha ancla del ranking, consistencia, margen, Zr): llevarlas a un ADR.
4. Modo B: falta la corrida Dr0 = 0 (`sensible_a_condicion_inicial`), `soil_carryover` y spin-up.
5. Escenarios de retraso: falta `buffer_days`; hoy la lluvia que sale del año agrícola se descarta y se reporta.
6. Alimentación e ingresos quedan `not_evaluable` hasta tener rendimientos de referencia, tabla de
   composición y precios con cita (no se inventan). El ranking usa agua + suelo (cobertura de pesos 0.5).
7. Pruebas: se usaron bucles con semilla en lugar de Hypothesis; se puede migrar sin cambiar invariantes.
