# Contrato del motor R2 → R3 (documentado en el README; a confirmar por R2)

R3 **no implementa ni copia** ET0, Pef, exposición, balance hídrico, cohortes, escenarios, ranking, estabilidad ni Soil VoI. Solo coordina, autoriza, persiste metadatos y transporta.

## 1. Fachada pública esperada (README §10)
```python
run_analysis(ctx: RunContext, scenario: ScenarioDef, adaptation: AdaptationMode) -> ScenarioRunResult
rank(ctx, results: list[StrategyRisk], weights: Weights, cfg: RankingConfig) -> RankingResult
rank_stability(ctx, inputs: RankingInputs, cfg: StabilityConfig) -> StabilityResult
soil_voi(ctx, parcel: SoilContext, strategies: list[Strategy], cfg: VoiConfig) -> VoiResult
build_report(ctx, bundle: AnalysisBundle, locale: Locale) -> ReportModel
```
`api.adapters.milpa_core.check_core_contract()` compara **nombres y orden de los primeros parámetros**. Comando: `python -m api.cli check-core` (hoy: «milpa_core: NO integrado», código 2).

## 2. Puerto de R3 (`api.adapters.ports.EnginePort`)
`run_base_analysis · run_scenarios · rank · soil_voi · build_report · summary · heatmap · dekad_chart · climate_history`. Entran/salen `Mapping[str, Any]` JSON. Sin R2: `NotIntegratedEngine` → 503 `DEPENDENCY_NOT_INTEGRATED`. Con un paquete compatible: `MilpaCoreEngine`, cuyos métodos están marcados `PENDING_R2` por los huecos de la sección 3.

## 3. Huecos que R2 debe cerrar
| # | Hueco | Impacto |
|---|---|---|
| 1 | Cómo construir `RunContext` (`RegionConfig, Catalogs, ClimateSeries, SoilContext, PriorityProfile, seed, hashes`) desde BD + Parquet | Bloquea `analysis_run`/`scenario_run` |
| 2 | Tipo de retorno de `run_analysis` (`ScenarioRunResult`) y cómo mapearlo a `engine.scenario_run/risk_summary/planting_summary` | Bloquea la persistencia de resultados |
| 3 | Funciones públicas que produzcan `StrategyRiskDTO[]`, `HeatmapDTO`, `DekadChartDTO` y el historial climático (no están en la fachada) | Bloquea `summary/heatmap/dekad-chart/climate-history` |
| 4 | API de **evidencia A/B/C** (`IndicatorBuilder`/reglas) para mediciones y declaraciones de suelo (`EvidencePort.provenance_for_soil`) | Bloquea guardar CSV/declaraciones (hoy `dry_run` valida) |
| 5 | `milpa_core.enums` (fuente canónica); `window_mode_t` existe en SQL pero no figura en README §15 | Sustituir el espejo provisional |
| 6 | `ReportModel` y su relación con `ReportDTO` (`sections`, `annex`) | Adaptador a la plantilla |
| 7 | Jerarquía de errores tipados (hoy se mapea por nombre) | Códigos `MIXED_CYCLE_LENGTH, MISSING_THRESHOLD_CITATION, INSUFFICIENT_SOIL_DATA, NOT_COMPARABLE` |
| 8 | Cuerpos de `POST /zones/{id}/runs`, `/runs/{id}/scenarios`, `/runs/{id}/soil-voi` (`params`, grilla de escenarios, `VoiConfig`) | Hoy `provisional_r3`/opacos |
| 9 | Semántica de `StabilityRequest.mode` y límites de `n_samples` | R3 solo fija un tope de seguridad (100 000) |
| 10 | Tolerancia numérica entre plataformas (ADR de reproducibilidad) | `make reproduce` |

## 4. Traducción de errores (implementada)
`MixedCycleLengthError→MIXED_CYCLE_LENGTH · MissingThresholdCitation→MISSING_THRESHOLD_CITATION · InsufficientSoilData→INSUFFICIENT_SOIL_DATA · NotComparable→NOT_COMPARABLE` (HTTP 422). Cualquier otra excepción se propaga como 500 genérico.

## 5. Reglas que R3 impone alrededor del motor
- Una lectura de escenario no calculado responde **409 `SCENARIO_NOT_COMPUTED`** y no llama al motor (prueba: `fake_engine.calls == []`).
- Las lecturas exigen corrida `ok` (`RUN_NOT_READY`) y acceso a la parcela de la corrida.
- Las cifras visibles conservan `ip_id`; el detalle sale de `GET /v1/provenance/{ip_id}` (forma del DDL; **no** es `ProvenanceInfo`).
- Los resultados Parquet se escriben por `run_id/scenario_id/adaptation` sin sobrescritura.

## 6. Pasos para integrar
1. Instalar `packages/milpa_core` en el workspace uv (R2). 2. `python -m api.cli check-core` debe dar OK. 3. Completar los métodos `PENDING_R2` con pruebas contra el paquete real (no dobles). 4. Reemplazar `provisional_enums` por `milpa_core.enums` (la prueba de paridad debe seguir verde). 5. Actualizar `INTEGRATION_STATUS.md` (solo entonces `integrated`).
