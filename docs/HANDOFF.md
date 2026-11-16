# Traspaso de contexto del proyecto (R3 + integración de R1 y R4)

> **Actualización 2026-11-16:** el motor `milpa_core` (R2) ya está integrado y cableado a la API (ADR-020): corridas, escenarios, ranking, VoI, informe, heatmap, gráfico por decena e historial climático salen del motor real; la sesión pública de demo está descrita en ADR-019. Estado vigente: `NEXT_STEPS.md` (raíz) y `docs/FINAL_PROJECT_AUDIT.md`.

Fecha del registro: 2026-11-15. Autor: asistente (modelo Sonnet 5.5) a petición del solicitante, **antes de cambiar de modelo**.
Regla de este documento: **nada se marca como completado si no fue verificado**. «Verificado» = se ejecutó en esta sesión y el resultado está citado. Lo demás figura como pendiente o sin verificar.

> Este archivo es la entrada de lectura obligatoria para quien continúe. Después leer, en este orden: `docs/integration/INTEGRATION_STATUS.md`, `docs/decisions/ADR-017…018`, `docs/TESTING.md` (§5-§7), `docs/auditoria/matriz_compatibilidad.md`, `docs/BACKEND_AUDIT.md` (§9-§11).

## 1. Qué es el proyecto y qué se pidió (instrucciones del solicitante, en orden)
1. **R3 (backend y plataforma)** de MILPA RESILIENTE 3.3: implementar BE-01…BE-11, ADR, documentación e integración según `README.md` (especificación integral), `Especificacion_Tecnica_MILPA_R3.md` y `CLAUDE.md`. Restricciones: sin Redis/Celery/ARQ/Dask/MinIO/Kubernetes; ADR para cambios de tecnología o contratos; no inventar contratos, datos científicos ni módulos ajenos; **no afirmar que algo funciona sin haberlo ejecutado**.
2. **Auditoría de R1/R3/R4** («reglas, compatibilidad e integración») con entregables en `docs/auditoria/`. Resultado clave: R1–R4 son **paquetes de trabajo, no estrategias agronómicas**; ningún entregable contiene parámetros agronómicos (todo `pending`, regla P9) y `milpa_core` (R2) no existe.
3. **Integración**: «implementa todo lo de `references/` en la carpeta raíz (el backend) siguiendo el README y la especificación técnica». Respuestas del solicitante: trabajar en la raíz con la estructura del README §23, **no crear R2** (un compañero lo enviará para la implementación final), integrar «todo lo actual». `references/` se conserva como referencia y **no se modificó** (salvo el caché `.git/index` de sus repos por comandos de lectura).
4. Este traspaso.

## 2. Mapa del repositorio (raíz = backend R3 + lo integrado)
| Ruta | Contenido | Dueño |
|---|---|---|
| `apps/api/` | FastAPI (34 operaciones), migraciones Alembic 0001–0014, plantillas del informe (provisional + las de R4) | R3 |
| `packages/milpa_etl/` | R1 portado (CLI `milpa-etl`), README propio, pruebas | R1 (integrado) |
| `catalogs/`, `regions/`, `data/curated/`, `data/demo/` | catálogos `pending`, region pack, serie real de `chiquimula_prueba` (ignorada por git), demo sintético rotulado + `EXPECTED.json` | R1 |
| `apps/web/` | SPA React de R4 + adaptadores (`src/api/adapters.ts`, `mock-wire.ts`) | R4 (integrado y adaptado) |
| `contracts/openapi.v0.draft.yaml` | borrador local de R4 (histórico; alimenta `draft.gen.ts` del mock y `r2_dto_draft.json`) | R4 |
| `tests/` (`contract`, `integration`, `privacy`, `acceptance`), `apps/api/tests/`, `packages/milpa_etl/tests/`, `testkit/` | pruebas | R3 / R4 |
| `docs/` | API, DATABASE, SECURITY, PRIVACY, JOBS, REPORTS, REPRODUCIBILITY, TESTING, DEPLOYMENT, DATA_SOURCES, ADD_A_REGION, `decisions/` (ADR-001…018), `integration/`, `auditoria/`, `r4/`, `openapi/`, `benchmarks/`, este archivo | R3 |
| `references/Milpa-Resiliente-R1`, `references/R4` | entregas originales (repos git ajenos). **No tocar** | R1 / R4 |
| `packages/milpa_core` | **NO EXISTE** (R2) | R2 |

**Git:** repositorio inicializado (rama `main`) con un único commit **`V1`** (366 archivos), pedido por el solicitante. `references/` (repos git ajenos de R1 y R4) está en `.gitignore` y no forma parte del commit; `data/demo/**` se marca `-text` en `.gitattributes` para que los hashes de `EXPECTED.json` no cambien por conversión de saltos de línea (verificado). `gitleaks protect --staged` sin hallazgos tras sustituir un token ficticio literal de una prueba. No hay remoto configurado ni se hizo `push`.

## 3. Verificado (con evidencia ejecutada)
| Qué | Resultado | Cuándo / cómo |
|---|---|---|
| **Suite completa en Docker/Linux** (`packages/milpa_etl/tests apps/api/tests tests`, PostGIS efímero, Pango real) | **410 aprobadas, 2 omitidas, 1 `xfail` (script 92 de R1), 0 fallos**, 10 min 23 s | tras todos los cambios de **código** (la imagen se construyó después de la tolerancia entre plataformas). Un aviso del sistema («detenida por poca memoria») llegó *después* del resumen de pytest |
| `ruff check`, `ruff format --check`, `mypy` estricto | limpio; 98 archivos de `src` | tras el último cambio de código |
| Frontend: `tsc -b`, ESLint, Vitest (26), linter de textos (8), `vite build` | 0 errores · limpio · 26/26 · 8/8 · OK | tras las últimas ediciones del frontend |
| Playwright (T-UI + T-A de R4, **contra el mock sintético**) | 27 aprobadas, 3 `fixme` de R4, 0 fallos | corrida completa tras corregir `testIgnore` y los ciclos de estrategia |
| R1: `milpa-etl selftest` | 24/24 | desde el paquete de la raíz |
| R1 → R3 con componentes reales | `seed catalog` (idempotente), `register zone` y lectura por la API (200 filas de cobertura, fuentes, comparaciones, `ea` 0,149) | ejecución manual contra PostgreSQL real; la API arrancó con la guardia de seguridad activa |
| `make reproduce` | 4 hashes de archivo + regeneración del `data_hash` con la ETL = `VERIFICADO`; **sale con código 3** por falta de R2 | host (Windows) y Docker (Linux, por tolerancia numérica) |
| `make -n` de 16 objetivos | OK | contenedor Debian |
| `gitleaks` | sin hallazgos en R3, R1 y R4 (incluido historial git de R1 y R4) | antes de la integración; **no repetido** sobre el árbol integrado |
| Pruebas de compatibilidad con artefactos reales | `tests/contract/test_r1_artifacts.py` 18 + 1 xfail; `test_r4_artifacts.py` 28 en Docker | |

## 4. Errores detectados (propios y ajenos)
### 4.1 Defectos de R3 (míos) — corregidos
| ID | Defecto | Corrección | Prueba |
|---|---|---|---|
| C-15 | Contrato de CSV de suelo propio (`SOIL_CSV_V0_PROVISIONAL`) cuando el README §9 ya lo define; yo lo había dado por «pendiente de R1» | `SOIL_CSV_V1` | `test_storage_hashing_csv.py`, `test_r1_artifacts.py` |
| — | `ProvenanceOut` con nombres de columnas, no del `ProvenanceInfo` (§15) | renombrado | `test_provenance_has_the_shape_…` |
| C-10 | Plantillas de ruta `{zone_id}` en vez de `{id}`/`{v}`/`{property}` (rompían clientes tipados) | alias `Path` | `test_r4_artifacts.py` |
| C-09 | Login sin `expires_in`/`role` | aditivo | `test_login_response_is_compatible_…` |
| S-01 (defensa) | R3 no comprobaba RLS al arrancar | `api.db.invariants` | `test_service_refuses_to_start_…` |
| — | `/reports/{id}/pdf` anunciaba también JSON | solo `application/pdf` | contrato |
| C-14 | CSS enlazado de la plantilla de R4 se perdía en silencio en el PDF | `inline_local_stylesheets` | PDF A4 en Docker |
| — | `load_ports()` exigía `Settings` (rompía trabajos en pruebas) | solo lee `Settings` si `ETL_INGEST_ENABLED` | suite Docker |
| — | Mis documentos citaban estadísticos de `validation_report.json` como si fueran de `precip_validation.json` | corregidos (SV-01/SV-06) | — |
| — | Afirmé dos veces cosas incorrectas en mensajes a la persona (CSV «pendiente de R1»; «la suite de Docker no terminó») | rectificadas en este traspaso y en `BACKEND_AUDIT.md` §10 / `TESTING.md` §7 | — |

### 4.2 Defectos o hallazgos en R1 (no corregidos en `references/`; mitigados en R3 cuando se pudo)
- **S-01 (seguridad, alta):** `sql/92_soil_fixture_provenance.sql` quita `security_invoker` de `soil.property_status` ⇒ un usuario sin parcelas veía 16 filas ajenas (demostrado). No se aplica; el servicio no arranca si ocurre. `xfail(strict)` lo documenta.
- C-01: los `sql/` no se aplican en orden de nombre. C-07: `ip_id NOT NULL` más estricto que el README. C-08: rama extra `desconocido` en la vista. C-13: `ingestar_suelo_db.py` escribe directo con evidencia fija y una regla (`soil_fixture_c`) que no existe en el catálogo. C-16: `data_hash` de R1 vs R3 no verificado.
- C-12: ET0 y Pef calculados en R1 (el README los asigna a R2). SV-04: ET0 negativo sin bandera.
- **SV-06:** `precip_validation.json` y `validation_report.json` dan estadísticos distintos para IMERG vs POWER.
- **SV-07:** `build-demo` no es idéntico bit a bit entre Windows y Linux (error relativo ≤ 4,6·10⁻¹⁶); `reproduce` aplica una tolerancia **provisional** (rtol 1e-9, atol 1e-12) a la espera de ADR.
- R1 no entrega `data/manifest/ingestions.jsonl` ni los JSON crudos ⇒ `register provenance` no puede ejecutarse con lo del repositorio.
- `seed_catalogo.py`/`fetch_dem.py` usaban `psycopg2` (portados a `psycopg` 3).
- **SV-01 (científico, abierto):** 81 % de los días de lluvia son POWER y 19 % IMERG, sin corrección de sesgo (bit 8 sin usar); `fallback_share_pct` ambiguo (SV-03).
- **SV-02:** sin Kc, fenología, umbrales, variedades, calendario ni zona (todo `pending`).

### 4.3 Hallazgos en R4 y en la especificación
- C-06: `/v1/healthz` en el borrador (la especificación fija `/healthz`). C-03/C-04/C-05: código de cancelación, listados desnudos, forma de la carga CSV. C-11: SPEC-01 (`Indicator` en toda cifra) es decisión local de R4 que cambia el §15; abierta con R2. Pruebas propias de R4 declaradas por R4 y ahora **re-ejecutadas** aquí (ver §3).
- `README.md` se modificó el 2026-11-15 00:40 (2 312 → 2 472 líneas) después de la auditoría inicial; no se sabe qué cambió.

## 5. Sin verificar / pendiente (NO marcar como hecho)
### 5.1 Ejecuciones no hechas
| # | Qué | Por qué falta |
|---|---|---|
| 1 | **Imagen `runtime` de Docker y `docker compose up` tras la integración** (Dockerfile con `milpa-etl`, `catalogs/`, `regions/`, copia de `data/demo` en el entrypoint, nuevas variables) | Solo se construyó la etapa `test`. **La imagen de producción nunca se construyó con los cambios ni se probó el arranque** |
| 2 | Suite completa del **host Windows** en una sola corrida tras los últimos cambios | Se corrió por grupos; las corridas completas del host fueron detenidas por memoria en dos ocasiones |
| 3 | **Ingesta real** (`fetch power/imerg`, `curate`, `validate` desde la red, token NASA) | Sin red/token en la sesión; `ProcessIngest` solo con ejecutor **falso** |
| 4 | `ProcessIngest` con `ETL_INGEST_ENABLED=true`: la consulta `_describe_zone` (SQL de zona) y el flujo del trabajo `zone_ingest` extremo a extremo | No hay prueba que ejercite esa SQL ni el trabajo real |
| 5 | **Playwright contra la API real** (solo se corrió contra el mock) | No se levantó API + SPA juntas |
| 6 | GitHub Actions (jobs `web`, `web-e2e` nuevos y los previos) y `pre-commit` | YAML validado, nunca ejecutado |
| 7 | `gitleaks` sobre el árbol integrado (ahora con `apps/web`, `packages`, `data`) | Solo se escaneó antes de integrar |
| 8 | `make data`, `make register`, `make seed`, `make web-*`, `make demo` ejecutados de verdad (solo `make -n`; `seed`/`register zone` se ejecutaron por CLI directo) | |
| 9 | Prueba con `data/curated` real en Docker | omitida (la carpeta no va en la imagen); sí corre en el host |
| 10 | Paridad TS (`make types`) en pytest | omitida con motivo (Node) |
| 11 | `npm audit` de R4 (vulnerabilidades de desarrollo declaradas por R4) | no revisado |
| 12 | Benchmarks (`docs/benchmarks`) tras la integración | no repetidos |
| 13 | `make test-docker` completo desde cero con la imagen reconstruida tras los últimos cambios **de documentos** (solo hubo cambios en docs, `regions/example_alt_region.yaml`) | no necesario para código; anotado por transparencia |

### 5.2 Código/diseño no hecho
- **R2 (`milpa_core`)**: inexistente. Hasta su llegada, los endpoints de análisis responden 503; `reproduce` sale con 3; Modo A/B, cohortes, heatmap, ranking, estabilidad, escenarios, Soil VoI y `report_model` no existen. Al llegar: instalarlo en el workspace, validar `check_core_contract`, sustituir los DTO `pending_r2`, recomputar `reproduce`, aprobar `EvidencePort`.
- Adaptador `report_model → contexto de la plantilla de R4` (depende de R2).
- Cifras simples (zona, calidad, suelo) se muestran con procedencia `desconocido` (no hay `Indicator` acordado, SPEC-01/C-11).
- Parquet: R3 lee el contrato **zonal** de R1; falta confirmación de R1/R2 sobre `cell_id` (README §13.7).
- Etapa de build del frontend en la imagen Docker (la API sirve `apps/web/dist` solo si existe).
- Endpoints de registro de usuarios y consentimiento (sin contrato); admin sin ruta de borrado (política DP-13).
- Validador del *region pack* (solo existe para catálogos); `data/manifest` real.
- `draft.gen.ts` (tipos del borrador de R4 para el mock) se generó a mano con `openapi-typescript`; **no hay script en `package.json`** que lo regenere.
- Tolerancia entre plataformas de `reproduce`: valor provisional, sin ADR de aprobación.

### 5.3 Decisiones/aprobaciones pendientes (del solicitante o de los roles)
ADR **003, 007, 009, 010, 015, 016, 017, 018** (propuestos, ninguno aprobado). Decisiones: Parquet por zona o por celda (R1+R2); lluvia primaria y sesgo (R2+asesor); `Indicator` en toda cifra (R2+R3); `DELETE /jobs` 200 vs 204, `Page[T]` vs listas, forma de la carga CSV (R3+R4); política de acceso/retención DP-13; DP-01…05, 12 (parámetros agronómicos).

### 5.4 Deuda documental (documentos con partes desactualizadas)
- `docs/DATABASE.md` y `docs/DEPLOYMENT.md` describen la cadena hasta la revisión **0013** (existe 0014, 14 revisiones) y no mencionan `apps/web`, `milpa_etl`, demo en imagen ni `ETL_INGEST_ENABLED`.
- `docs/API.md` no refleja: `GET /runs/{id}/scenarios` como `ScenarioTag[]`, `soil-voi` con cuerpo opcional, `RunOut` ampliado, `StrategyOut.latest_version`, `DataQualityOut`/`ZoneDetail` ampliados.
- `docs/JOBS.md`: `zone_ingest` ahora tiene adaptador por proceso (no documentado).
- `docs/auditoria/`: llevan una nota de actualización, pero partes del cuerpo describen el estado **previo** a la integración: `inventario_documental.md` («`packages/milpa_etl` no existe»), `auditoria_R3.md` (R3-F12 «Incompatible»), `informe_validacion.md` §1-§5, `plan_integracion.md` (varias acciones ya hechas), `matriz_trazabilidad.md`. La verdad vigente está en `INTEGRATION_STATUS.md`, `TESTING.md` §7 y este archivo.
- `docs/r4/` es copia de la documentación de R4 sin revisar (cita rutas de su repositorio original).

## 6. Entorno y trampas operativas
- **Memoria:** el sistema ha detenido corridas largas «por poca memoria» al menos 4 veces (suite del host, Docker). Instrucción vigente: **no relanzar por cuenta propia**; ejecutar por grupos o con memoria libre.
- **Shell:** los heredocs con comillas anidadas fallan en esta herramienta; usar escritura de archivos + script Python. En Git Bash usar `MSYS_NO_PATHCONV=1` para `docker`. `uv` está en `C:\Users\MM\AppData\Roaming\Python\Python313\Scripts\uv.exe`; el entorno es `.venv\Scripts\python.exe`; la CLI `milpa-etl` en `.venv\Scripts\milpa-etl.exe`.
- **PostGIS de pruebas:** contenedor `milpa-test-db` (puerto 55432, `postgres` / `postgres_test_only`; rol `milpa_app` / `app_test_only`). Bases sobrantes de pruebas: `r1_ddl`, `r3_ddl`, `r3_seed` y `milpa_test_*` (de corridas interrumpidas). Limpieza segura: `DROP DATABASE … WITH (FORCE)`. Imágenes locales: `milpa-app:test`, `milpa-app:local`, `milpa-db:local`.
- **Frontend:** `node_modules` de la raíz es copia de la de R4 (242 MB); Playwright en Windows usa `PLAYWRIGHT_CHROMIUM_EXECUTABLE="C:\Program Files\Google\Chrome\Application\chrome.exe"`. `apps/web/src/api/types.gen.ts` se genera desde `docs/openapi/openapi.json` (`npm run web:types`).
- **OpenAPI:** regenerar con `python -m api.cli openapi --out docs/openapi/openapi.json` (necesita `JWT_SECRET` y `DATABASE_URL` en el entorno) cada vez que cambien DTO; luego regenerar tipos.
- `data/*` está en `.gitignore` salvo `data/demo/`; `data/curated` es local.

## 7. Cómo retomar y verificar (orden recomendado)
1. `make lint` y `make test-unit` (host). 2. `make test-docker` con memoria libre (cifra final única; la última fue 410/2/1/0). 3. `make test` (host) por grupos si hay poca memoria. 4. Construir la imagen runtime y probar `docker compose up` (§5.1-1). 5. `npm run web:test:e2e` y una corrida contra la API real (§5.1-5). 6. `gitleaks` sobre el árbol integrado. 7. Probar `ETL_INGEST_ENABLED=true` con una zona de prueba y un ejecutor real o falso a nivel de trabajo. 8. Esperar R2 y repetir `check-core`, `reproduce` y la matriz de integración. 9. Pedir al solicitante las aprobaciones de §5.3 y registrar el resultado en los ADR.
