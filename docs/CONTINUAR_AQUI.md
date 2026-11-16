# CONTINUAR AQUÍ — estado al 2026-11-15 (traspaso a otro Claude)

Raíz del repo: `C:\Users\MM\Desktop\milpa-resiliente` (rama `main`, único commit `e37c3dd V1`).
Lee primero: `CLAUDE.md`, `README.md` (fuente de verdad), `docs/HANDOFF.md`, `docs/integration/INTEGRATION_STATUS.md`
y la memoria `C:\Users\MM\.claude\projects\C--Users-MM-Desktop-milpa-resiliente\memory\`.

> R1–R4 son **paquetes de trabajo** (R1 datos, R2 motor `milpa_core`, R3 backend = `apps/api`, R4 frontend), **no estrategias**.
> Las estrategias son entradas del catálogo (`ref.strategy`; README §11.6). Las del piloto R2 son E1–E7.

## 0. Petición vigente del usuario (MASTER EXECUTION PROMPT)
Llevar el proyecto a estado integrado, funcional y listo para NASA Space Apps: un backend, un motor, una API, un frontend de 4 pantallas
(Mi zona, Cómo cambió el calendario, Laboratorio de rotaciones, Informe de decisión). Reglas duras:
- **No** borrar/modificar `references/` (solo lectura). **No** inventar datos ni valores agronómicos (P9: `pending` sigue `pending`).
- Datos sintéticos **solo** en pruebas aisladas y rotuladas; nunca en dashboard, informes, mapas ni evidencia NASA.
- Pedir autorización **antes** de acciones destructivas (borrar archivos, reemplazar BD, quitar volúmenes, sobrescribir datos).
- No publicar tokens/claves. No decir "COMPLETADO" sin evidencia ejecutada. No hacer commit salvo que el usuario lo pida
  (si se hace: terminar el mensaje con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`).
- Entregable final: `docs/FINAL_PROJECT_AUDIT.md` con matriz de cumplimiento del README
  (COMPLETADO Y VERIFICADO / IMPLEMENTADO, PENDIENTE DE VALIDACIÓN / PARCIALMENTE IMPLEMENTADO / BLOQUEADO POR DEPENDENCIA EXTERNA / NO IMPLEMENTADO),
  estado inicial/final, fuentes reales conectadas, pruebas ejecutadas, bugs corregidos, límites, credenciales faltantes, instrucciones de ejecución/despliegue.

## 1. Lo que YA se hizo en esta sesión (verificado salvo indicación)

### 1.1 Corrección del orden de ingesta R1 (verificado)
- `apps/api/src/api/adapters/etl_process.py`: orden `fetch power → curate → validate → [fetch imerg → merge imerg]` (R1 exige curar antes del merge).
- `apps/api/tests/test_etl_process.py` actualizado + prueba `test_real_r1_cli_accepts_the_arguments_this_adapter_sends` (marca `slow`, usa `curate`/`validate` reales de R1; pasó en ~22 s).
- `tests/integration/test_hardening.py`: `test_etl_ingest_reads_the_zone_from_postgis_and_is_opt_in` (pasó).

### 1.2 Integración inicial de R2 en la raíz (copiado, SIN tocar `references/R2`)
Copiado: `packages/milpa_core/` (src, tests, pyproject; nombre de distribución cambiado a `milpa-core`), `tools/r2/*.py` (calibrate_sandbox_thresholds, make_synthetic, milpa_adapter, r2_run),
`catalogs/r2/{crops,ph_tolerance,thresholds}.yaml`, `regions/r2/pilot_corredor_seco{,.strategies}.yaml`, `docs/r2/{METHODS.md,README_R2.md,examples/}`, `tests/integration/test_r2_adapter_e2e.py`.
- Los catálogos/región de R2 van en subcarpetas `r2/` **a propósito**: `catalogs/crops.yaml` y `regions/pilot_corredor_seco.yaml` de R1 son plantillas `pending` y los usa un test de R1 (`packages/milpa_etl/tests/test_cli_and_data.py`); no se reemplazan.
- `pyproject.toml` raíz: `milpa_core` añadido a `[tool.uv.workspace].members`. `apps/api/pyproject.toml`: dependencias `pyyaml` y `milpa-core` (+ `[tool.uv.sources] milpa-core = { workspace = true }`).
- `uv lock` OK (138 paquetes, "Added milpa-core v0.1.0"); `uv sync --all-packages --all-groups` OK.
- **Verificado:** `packages/milpa_core` → **57 passed** en 5 s (ejecutado desde `packages/milpa_core` con la config de pytest de R2). 
- **Verificado:** `tests/integration/test_r2_adapter_e2e.py` → **2 passed** (rutas de `tools/r2/r2_run.py` y `calibrate_sandbox_thresholds.py` ajustadas al layout de la raíz: `regions/r2`, `catalogs/r2`, salida por defecto `docs/r2/examples`). Total R2 = 59 pruebas verdes (R2 declaraba 58).

### 1.3 Notas de entorno
- `uv` NO está en el PATH del host. Lo instalé temporalmente con `.venv/Scripts/python.exe -m pip install uv` (`.venv/Scripts/uv.exe`); el `uv sync` lo desinstaló (no es dependencia). Para reusar: reinstalarlo igual, o usar Docker (`make test-docker`).
  Con `UV_PROJECT_ENVIRONMENT=.venv` en Git Bash.
- `uv.lock` aparecía modificado solo por espacios en blanco/CRLF; lo revertí con `git checkout` y luego se regeneró de verdad por `milpa-core`.
- **RAM del equipo muy baja** (≈140–380 MB libres): las corridas largas fueron matadas varias veces. Ejecutar por grupos; no relanzar solas las matadas.
- `infra/scripts/smoke-compose.sh` (nuevo, sin commit): prueba de humo de `docker compose`; **su ejecución se interrumpió, resultado desconocido**. `sh -n` OK.

## 2. Qué FALTA (en orden recomendado)

### A. Terminar la integración de R2 (siguiente paso inmediato)
1. (HECHO) `test_r2_adapter_e2e.py` pasa desde la raíz. Pendiente: correr `tools/r2/r2_run.py --daily data/curated/chiquimula_prueba/daily.parquet --out <tmp>` con la serie curada real de R1.
2. Mover el cargador de E/S a la API: crear `apps/api/src/api/adapters/core_io.py` basado en `tools/r2/milpa_adapter.py` (`load_region`, `load_catalogs`, `load_strategies`, `load_curated_daily`). No duplicar ciencia: solo E/S.
   - Contrato R1↔R2: el `daily.parquet` real de R1 **no tiene `cell_id`** y `obs_date` es timestamp; el adaptador de R2 ya lo tolera (alias + `cell_id="cell"`), verificar con la serie curada de `data/curated/chiquimula_prueba/` (la zona real, sin sintéticos).
3. Cablear `apps/api/src/api/adapters/milpa_core.py` (`MilpaCoreEngine`): hoy todos los métodos lanzan `PENDING_R2`. R2 ya expone: `make_context, run_analysis, rank, rank_stability, soil_voi, run_grid, standard_grid, BASE`, DTOs en `milpa_core.dto` (`run_summary_dto`, `rank_response_dto`), `planting.heatmap_cycle/heatmap_strategy`, `exposure.dekad_chart`, `report_model.build_report`, `facade.compare_to_base`, `humidity_sensitivity_flags`. Ver `tools/r2/r2_run.py` como receta.
   - `DOCUMENTED_FACADE` en ese archivo usa firmas del README (`ctx, results, weights, cfg`…) que **no coinciden** con las reales (`rank(ctx, run, weights, cfg, ...)`, `soil_voi(ctx, run, base, ...)`, `build_report` está en `milpa_core.report_model`). Corregir `check_core_contract`/`python -m api.cli check-core` a lo real y documentar la discrepancia (no inventar).
4. Persistir corridas: `engine.analysis_run`, `scenario_run`, resultados Parquet bajo `DATA_DIR`; jobs (`engine.job` + ProcessPoolExecutor) para corrida base y grilla de 45 escenarios; devolver DTO reales en summary/heatmap/dekad-chart/rank/soil-voi/scenarios/report. Reemplazar los borradores `pending_r2` del OpenAPI (`api/contracts/r2_dto_draft.json`) por los DTO reales; regenerar `apps/web/src/api/types.gen.ts`.
5. `make reproduce` hoy sale con código 3 porque faltaba R2: recalcular y verificar con el motor real; quitar `run-base/scenarios` "blocked" del Makefile y fusionar `references/R2/Makefile.r2` (objetivos `test-science`, `run-base`, `scenarios`, `examples`, `enums-sql`).
6. Verificar paridad `enums.sql/json` de R2 con las migraciones (T-C); ADR nuevo (p. ej. ADR-019) para: integración de `milpa_core`, ubicación `catalogs/r2` y `regions/r2`, uso de uv workspace. Las decisiones marcadas **[Propuesto R2]** en `docs/r2/METHODS.md` requieren ADR/confirmación; todo sigue `sandbox`/evidencia C (umbrales calibrados para serie sintética, Kc FAO-56 candidatos con `citation: null`).
7. Añadir `milpa_core` a ruff/mypy estricto (CLAUDE.md §6) — hoy `packages/**` está excluido de ruff; mypy estricto solo cubre `api`. Revisar qué rompe y corregir sin cambiar la ciencia.

### B. Datos reales (prioridad máxima del prompt)
- NASA POWER (sin clave, necesita red) para la zona piloto vía `ProcessIngest`/`milpa-etl`; DEM Copernicus (`rasterio`); IMERG **bloqueado sin `EARTHDATA_TOKEN`** (pedir al usuario solo si es indispensable; nunca guardarlo en el repo).
- SoilGrids (README nivel A): no implementado en R1. Resto de fuentes (MODIS, HLS, SMAP, NEX-GDDP, Landsat, Sentinel, MAGA/INAB/SEGEPLAN): evaluar contra el README e implementar solo con función concreta; si no, documentar como NO IMPLEMENTADO / BLOQUEADO. Sin conexión → mostrar estado de disponibilidad, nunca datos falsos.
- Registrar zona piloto/catálogos/estrategias en la BD (`make register` requiere rol propietario).

### C. Frontend (R4 ya integrado en `apps/web`)
- Localizar y **leer** antes de diseñar (no afirmar uso si no se leyó): skills de Emil Kowalski (`emil-design-eng`), Taste (`design-taste-frontend`), Impeccable (están en `references/R4/.claude/skills/`) y las `ui-ux-pro-max:*` (vía Skill tool). Elegir UNA librería de animación (Motion o GSAP), respetar `prefers-reduced-motion`.
- Índice + 4 pantallas con estados cargando/vacío/error, filtros, gráficos con título, unidades, periodo, fuente, leyenda, observado-vs-simulado, datos faltantes; responsive y accesible; nada hardcodeado que sustituya resultados del backend. Hoy Playwright corre contra el mock, **no** contra la API real.

### D. Auditoría de código pendiente (petición anterior del usuario)
- `packages/milpa_etl` (R1; excluido de ruff del proyecto) tiene 16 hallazgos sin corregir: F841 `last_err` (`core.py:190`), B905 `zip(strict=)` ×6, F401 `date/timedelta` (`imerg.py:34`), B023 cierres en bucle (`imerg.py:268/282/669`, **inspeccionar**), B007 (`dem.py:418`), F841 `n` (`register_provenance.py:67`).
- `pip-audit`, `npm audit`, revisión de seguridad/rendimiento, gitleaks sobre el árbol integrado.

### E. Verificaciones adeudadas (nada de esto está confirmado tras integrar)
- Suite completa (último resultado verificado, ANTES de esta sesión: Docker 410 passed / 2 skipped / 1 xfail / 0 failed). Ruff y mypy estricto desde los últimos cambios; `make test-docker`.
- `infra/scripts/smoke-compose.sh` completo (imagen runtime + `docker compose up`); la imagen debe incluir `milpa-core` (revisar `infra/Dockerfile.app` y `uv sync --frozen`).
- Playwright contra API real; GitHub Actions nunca ejecutado; ingesta real con red/token.
- ADRs pendientes de aprobación humana: 003, 007, 009, 010, 015, 016, 017, 018.

### F. Documentación
- Actualizar `docs/HANDOFF.md`, `docs/integration/INTEGRATION_STATUS.md`, `docs/DATABASE.md`/`DEPLOYMENT.md` (solo llegan a la migración 0013; hay 0014), `docs/API.md`, `docs/JOBS.md`, docs de auditoría parcialmente obsoletos y la memoria (R2 ya **no** está ausente: se integró el 2026-11-15, aún sin cablear a la API).
- Escribir `docs/FINAL_PROJECT_AUDIT.md` al final.

## 3. Trampas conocidas
- `references/.../sql/92_soil_fixture_provenance.sql` (R1) quita `security_invoker` y filtra por RLS: **no aplicar**; `api.db.invariants` impide arrancar si ocurre.
- `build-demo` produce un hash distinto en Windows vs Linux (ruido ≤4.6e-16): `reproduce` compara con tolerancia (rtol 1e-9, atol 1e-12, provisional).
- Heredocs con comillas fallan en este shell: usar Write + scripts Python. En Docker bajo Git Bash usar `MSYS_NO_PATHCONV=1`.
- `data/curated/` ignorado por git; `data/demo/**` con `-text` (no tocar finales de línea).
