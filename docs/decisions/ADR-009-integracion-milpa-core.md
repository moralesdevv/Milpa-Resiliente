# ADR-009: Integración con `milpa_core` (R2)

- **Fecha:** 2026-11-14 · **Estado:** **propuesto — requiere aprobación de R2** (frontera entre componentes)

## Contexto y problema
`milpa_core` (R2) no existe todavía. La fachada pública documentada (README §10) es `run_analysis, rank, rank_stability, soil_voi, build_report`; **no** publica funciones para construir `StrategyRiskDTO`, `HeatmapDTO`, `DekadChartDTO` ni el historial climático, ni cómo ensamblar `RunContext` desde datos curados. R3 no puede inventar nada de eso.

## Decisión
1. **Puertos** (`api.adapters.ports`): `EnginePort`, `EvidencePort`, `IngestPort`. Los routers solo conocen servicios; los servicios, solo puertos. Los datos cruzan el puerto como `Mapping[str, Any]` JSON (los DTO son de R2).
2. **Implementación por defecto** `NotIntegrated*`: lanza `DependencyNotIntegrated` → 503 `DEPENDENCY_NOT_INTEGRATED` (o fallo tipado del trabajo). **Nunca** resultados simulados.
3. **`MilpaCoreEngine`** (`adapters/milpa_core.py`): se selecciona solo si `milpa_core` se importa **y** `check_core_contract()` confirma las firmas documentadas; el comando `python -m api.cli check-core` informa discrepancias. Sus métodos están marcados `PENDING_R2` porque faltan contratos de R2 (ensamblado de `RunContext`, constructores de DTO de presentación, tipo de retorno de `run_analysis`).
4. **Evidencia A/B/C (C5):** `prov.indicator_provenance` exige `evidence_level` salvo `desconocido`, y el nivel lo decide R2. R3 **no lo asigna**: guardar mediciones/declaraciones de suelo exige `EvidencePort` (503 si falta; `dry_run` valida sin guardar).
5. **Enums (C6):** espejo provisional `api.contracts.provisional_enums` (solo lo listado en README §15/§13.1), con prueba de paridad Python↔SQL↔OpenAPI. Se reemplazará por `milpa_core.enums`.
6. Dobles de prueba (`testkit/doubles.py`) viven fuera de `src/` y se rotulan `TEST DOUBLE`.

## Alternativas
Copiar el motor (prohibido), calcular «aproximaciones» en la API (prohibido), mock con datos plausibles (prohibido).

## Consecuencias / riesgos
(+) Integración posterior sin reestructurar. (−) Hasta entonces BE-06 está `adapter_ready`, no `integrated`. Riesgo: DTO de R2 incompatibles con el frontend → el contrato OpenAPI marca esos esquemas `pending_r2`.

**Aprobadores:** R2, R3.
