# Pruebas y calidad (BE-01, BE-08, T-*)

Regla: **una prueba omitida no es una prueba aprobada.** Cada ejecución se informa como *aprobada / fallida / omitida / bloqueada*. Los resultados reales de la última ejecución están en la sección 5.

## 1. Niveles y dónde viven
| Nivel | Herramienta | Ubicación | Necesita |
|---|---|---|---|
| Unitarias `T-U` y propiedades `T-P` | pytest + Hypothesis | `apps/api/tests/` | nada |
| Integración `T-I` | pytest + **PostgreSQL 16/PostGIS real**, rol real de la app | `tests/integration/` | PostGIS |
| Seguridad y privacidad `T-S` | pytest | `tests/privacy/`, `tests/integration/test_rls.py`, `test_api_auth.py` | PostGIS |
| Contrato `T-C` | OpenAPI, paridad de enums, fronteras, **Schemathesis** | `tests/contract/` | PostGIS (paridad, Schemathesis) |
| PDF | pytest | `apps/api/tests/test_reports_pdf_reportlab.py`, `test_report_from_engine.py`, `tests/integration/test_reports_pdf.py` (ReportLab: sin Pango); marca `pdf` = ruta HTML opcional | Pango solo para la ruta HTML |
| Rendimiento `T-B` | `python -m api.bench` | `apps/api/src/api/bench/` | PostGIS |
| Aceptación `T-A`, UI `T-UI` | — | R4 (`tests/acceptance/` vacío) | **bloqueado** |
| Ciencia `T-P`/`T-G` de `milpa_core` | — | R2 | **bloqueado** |

Datos de prueba: filas **sintéticas** creadas por `testkit/` (marcadas como pruebas); dobles (`testkit/doubles.py`) etiquetados «TEST DOUBLE», nunca importados desde `src/`.

## 2. Cómo ejecutar
```bash
make setup                     # uv sync --frozen --all-packages --all-groups
make lint                      # ruff check + ruff format --check + mypy (estricto)
make test-unit                 # sin base de datos
# PostGIS de pruebas (host): una vez
docker run -d --name milpa-test-db -e POSTGRES_PASSWORD=postgres_test_only -p 127.0.0.1:55432:5432 postgis/postgis:16-3.4
make test                      # todo lo que no requiere Pango (usa TEST_DATABASE_ADMIN_URL; por defecto 127.0.0.1:55432)
make test-docker               # suite completa en la imagen (PDF incluido) contra un PostGIS efímero
make bench                     # benchmarks
```
Variables: `TEST_DATABASE_ADMIN_URL` (superusuario del PostGIS de pruebas), `TEST_APP_ROLE` / `TEST_APP_ROLE_PASSWORD` (por defecto `milpa_app` / `app_test_only`; el rol se crea si falta). Cada sesión crea y borra una base `milpa_test_<id>` migrada con Alembic desde cero. Si PostgreSQL no está disponible, las pruebas `integration` se **omiten con motivo**.

## 3. Qué comprueban las pruebas de seguridad (mapa a los requisitos mínimos de la especificación §21.2)
| Requisito | Prueba |
|---|---|
| Migración desde base vacía / reversible | `test_migrations.py` |
| Dos usuarios no acceden a lo del otro | `test_rls.py`, `test_api_parcels.py`, `test_api_analysis.py` |
| Técnico sin asignación/consentimiento no accede | `test_rls.py::test_assigned_technician…`, `…withdrawn_consent…`, `…other_purpose…` |
| RLS con el rol real de la app; sin BYPASSRLS | `test_application_role_cannot_bypass_rls` |
| `SET LOCAL` no se filtra entre transacciones | `test_context_does_not_leak_*` |
| Job duplicado con misma clave no duplica | `test_idempotency_key_*` |
| Job `running` huérfano se recupera | `test_orphan_recovery_*` |
| Archivo fuera de `DATA_DIR` rechazado | `test_store_blocks_*`, Hypothesis `test_store_resolve_never_escapes_root` |
| Hash incorrecto rechaza el artefacto | `test_parquet_hash_verification…`, descarga de PDF |
| CSV grande / mal formado con detalle por fila/campo | `test_csv_*` |
| WeasyPrint no accede a recursos no permitidos | `test_ssrf_attempts_in_html_are_blocked…` (Docker) |
| PDF público sin datos personales ni coordenadas | `test_public_pdf_text_has_no_personal_data…` (Docker) |
| Informe generado y SHA-256 registrado | `test_generate_registers_hash…` (Docker) |
| OpenAPI valida con Schemathesis | `test_schemathesis.py` |
| Sin secretos en repo/logs | `test_privacy_leaks.py`, gitleaks en CI |

## 4. Lo que NO está probado (honestamente)
- GitHub Actions: el workflow está escrito y su YAML validado, pero **no se ha ejecutado** (el directorio no es un repositorio Git y no hay remoto).
- `pre-commit`: configurado, no ejecutado.
- `make types` (`openapi-typescript`): **no ejecutado** (descarga de paquete npm no autorizada en esta sesión); la prueba de paridad TypeScript se omite.
- Integración real con R1, R2 y R4: no existe ninguno de los tres.
- Rendimiento de ranking/heatmap/matriz base/grilla de escenarios: depende de R2.
- Pruebas de penetración y revisión legal de privacidad.

## 5. Resultados reales (2026-11-15)
| Ejecución | Resultado | Notas |
|---|---|---|
| **Docker/Linux, suite completa** (`infra/scripts/test-docker.sh`, PostGIS 16.4/3.4 efímero, Pango real) | **310 aprobadas, 1 fallida, 2 omitidas** | La fallida era un defecto de la propia prueba (`run_id` inexistente en `test_reports_pdf.py`). Corregida y repetida en Docker: `test_reports_pdf.py` + `test_reports.py` = **21 aprobadas**. |
| Host Windows, suite completa (anterior a las pruebas de privacidad/Schemathesis/endurecimiento) | 233 aprobadas, 7 omitidas, 0 fallidas | Omitidas: 5 PDF (sin Pango en el host), 1 symlinks, 1 tipos TS. |
| Host, por grupos tras los últimos cambios | aprobadas | RLS+migraciones+privacidad (43), Schemathesis (2), contrato/OpenAPI/mock, endurecimiento (18), reproducibilidad (12), adaptadores (11), fronteras (12), configuración (26). |
| `ruff check` / `ruff format --check` | limpio (177 archivos) | |
| `mypy` estricto | limpio (95 archivos) | última ejecución completa antes de los cambios de CORS/Dockerfile; la prueba de configuración posterior pasó |
| `pip-audit` sobre `uv.lock` | sin vulnerabilidades conocidas | |
| `gitleaks` (todo el directorio) | sin hallazgos | tras renombrar 2 falsos positivos de pruebas/benchmark |
| `docker compose up` real | OK | `/healthz` 200; `milpa_app` sin superusuario/BYPASSRLS; 48 tablas, revisión 0013; uid 10001; BD sin puertos; login y reinicio; PDF con SHA-256 idéntico en dos contenedores |
| `make -n` (13 objetivos) y objetivos bloqueados de R1/R2/R4 | OK | los bloqueados salen con código 2 |
| Benchmarks | ver `docs/benchmarks/LATEST.md` | RLS `count(*)` 10 000 filas: 4 840 ms → 23 ms (p50) |

**No hay una ejecución completa y final única tras el último cambio:** las dos últimas corridas completas del host fueron detenidas por el sistema por falta de memoria (no por fallos de pruebas). Antes de dar R3 por cerrado, ejecutar `make test` (host) y `make test-docker` en una máquina con memoria libre.

## 6. Auditoría de integración (2026-11-15) — resultados posteriores a la sección 5
Detalle y cómo reproducir: `docs/auditoria/informe_validacion.md`. Nuevas suites con **artefactos reales** de R1/R4 (`tests/contract/test_r1_artifacts.py`, `test_r4_artifacts.py`; se omiten con motivo si `references/` no existe).

| Ejecución | Resultado |
|---|---|
| ruff / ruff format / mypy estricto | limpio (144 / 96 archivos) |
| Unitarias del host | 129 aprobadas, 6 omitidas |
| Contrato + privacidad del host | 114 aprobadas, 3 omitidas, 4 `xfail` intencionales (defectos de R1: Parquet sin `cell_id` ×3, script 92) |
| `test_r4_artifacts.py` en Docker (con PDF) | 28 aprobadas |
| Integración del host | **sin resultado final tras los últimos cambios** (la corrida fue detenida por memoria); ejecuciones dirigidas posteriores: todas verdes |
| Suite completa en Docker | **no ejecutada tras estos cambios**; la etapa `test` ahora copia `references/` (R1 completo sin `.git`; de R4 solo `contracts` y `apps/api`) |

Pendiente: ejecutar `make test` y `make test-docker` con memoria libre para obtener una cifra única final.

## 7. Integración de R1 y R4 en la raíz (2026-11-15, ADR-018)
Cifras de ejecuciones **reales** de esta etapa (no hay corrida única final de toda la suite; ver al pie).

| Ejecución | Resultado |
|---|---|
| `milpa-etl selftest` (R1, desde el paquete de la raíz) | 24/24 OK |
| `pytest packages/milpa_etl/tests apps/api/tests/test_etl_process.py` | 22 aprobadas |
| `make reproduce` con `data/demo` real | 5 comprobaciones `VERIFICADO` (4 hashes de archivo + `data_hash` regenerado con la ETL); código 3 por falta de R2 |
| Pruebas con datos reales de R1 (`test_api_analysis.py::…real_r1…`, `test_r1_artifacts.py`) | aprobadas (18 + 1 `xfail` del script 92) |
| `seed catalog` y `register zone` de R1 contra PostgreSQL real | OK; `seed` idempotente |
| Verificación manual cargador de R1 → BD → API | zona `chiquimula_prueba`: 200 filas de cobertura, fuentes, comparaciones, `ea` 0,149 |
| Frontend: `tsc -b` · ESLint · Vitest · linter de textos · `vite build` | 0 errores · limpio · 26/26 · 8/8 · OK |
| Frontend: Playwright (T-UI y T-A, fixture sintético rotulado) | 27 aprobadas, 3 `fixme` de R4, 0 fallos |
| Make: `make -n` de los objetivos nuevos (Debian) | 16 objetivos OK |
| **Suite completa en Docker/Linux** (`make test-docker`: `packages/milpa_etl/tests apps/api/tests tests`, PostGIS efímero, Pango real) tras los últimos cambios de código | **410 aprobadas, 2 omitidas, 1 `xfail` (script 92 de R1), 0 fallos** — 10 min 23 s. Incluye PDF, Schemathesis, RLS, reproducción con tolerancia entre plataformas (Linux regenera el demo generado en Windows) |
| Omitidas en Docker | paridad de tipos TS (`make types`, depende de Node) y la prueba con `data/curated` real de R1 (esa carpeta no va en la imagen); ambas se ejecutan en el host |

Nota: el sistema emitió un aviso de «detenida por poca memoria» para esa corrida DESPUÉS de que pytest imprimiera su resumen; el resultado de arriba es el del registro completo. Lo único sin repetir tras los últimos cambios es la suite completa del host Windows (se ejecutaron por grupos). Límites: Playwright **no** se ejecutó contra la API real; la ingesta de NASA no se ejecutó (sin red/token); GitHub Actions y `pre-commit` no se ejecutaron; ver al pie de la sección 5 y la `informe_validacion.md`.

> **Qué falta ejecutar y qué NO está verificado: `docs/HANDOFF.md` §5.1** (imagen `runtime` y `docker compose up` tras la integración, ingesta real, Playwright contra la API real, CI de GitHub, `gitleaks` del árbol integrado, suite completa del host en una sola corrida).
