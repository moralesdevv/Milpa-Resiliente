# Informe de validación (FASE 7)

> **Actualización posterior (ADR-018):** R1 y R4 se integraron en la raíz del repositorio (`packages/milpa_etl`, `apps/web`, `catalogs/`, `regions/`, `data/`). El contrato Parquet zonal de R1 es ahora el que lee R3 (C-02 resuelto en R3; la diferencia con el README §13.7 queda registrada). Las cifras de este documento corresponden a la auditoría previa a esa integración salvo donde se indique.

Fecha: 2026-11-15. Todo lo de esta tabla fue **ejecutado** en esta sesión salvo lo indicado como «declarado» o «no ejecutado». Entorno: Windows 11 (host), Python 3.12.16, PostgreSQL 16.4 + PostGIS 3.4.3 en contenedor (`milpa-test-db`), Docker (imagen `milpa-app:test` con Pango/WeasyPrint 70), Node v24.14.1 con las herramientas ya instaladas en `references/R4/node_modules`.

## 0. Alcance de este informe
Las secciones 1-5 describen la auditoría ANTERIOR a la integración de `references/` en la raíz. Los resultados de la integración (ADR-018) están en `docs/TESTING.md` §7 y en `docs/integration/INTEGRATION_STATUS.md`.

## 1. Resultado honesto sobre la corrida final

**No existe una corrida completa y única de toda la suite tras el último cambio.** La última corrida por tandas fue detenida por el sistema por memoria insuficiente (no por fallos de pruebas) mientras ejecutaba la tanda de integración. No se relanzó. Lo que sí terminó, tras los últimos cambios de código:

| Comprobación | Resultado |
|---|---|
| `ruff check` + `ruff format --check` (144 archivos) | limpio |
| `mypy` estricto (96 archivos de `src`) | limpio |
| Unitarias `apps/api/tests` | **129 aprobadas, 6 omitidas** (5 PDF sin Pango, 1 symlinks) |
| Contrato + privacidad `tests/contract tests/privacy` (incl. Schemathesis y las nuevas pruebas con R1/R4) | **114 aprobadas, 3 omitidas, 4 `xfail` intencionales, 0 fallos** |
| Integración `tests/integration` | **Sin resultado final** (corrida detenida). Última corrida completa, ejecutada mientras se hacían los últimos cambios: 123 aprobadas, 4 omitidas, 0 fallos |
| Integración, ejecuciones dirigidas posteriores a los cambios | `test_api_auth.py` 17 aprobadas · `test_hardening.py` 19 · `test_api_parcels.py` + CSV + privacidad (88 aprobadas, 2 omitidas) · `test_api_analysis.py -k provenance` 2 · todas con 0 fallos |
| `tests/contract/test_r4_artifacts.py` en Docker (incluye PDF A4) | **28 aprobadas** |
| Suite completa en Docker (`make test-docker`) | **No ejecutada tras estos cambios** (la imagen de pruebas ahora copia `references/`; no se reconstruyó) |

Omitidas ≠ aprobadas: las 5-6 pruebas de PDF solo corren en Docker.

## 2. Mediciones de compatibilidad (reproducibles)

| Medición | Resultado | Cómo reproducir |
|---|---|---|
| Autopruebas de R1 | 24/24 OK; ET0 Ejemplo 18 FAO-56 = 3,88 (ref. 3,9) | `DATA_DIR=<tmp> python references/Milpa-Resiliente-R1/milpa_r1.py selftest` |
| CSV de R1 con el validador de R3 | 7 filas válidas aceptadas; 9 inválidas rechazadas con su error | `pytest tests/contract/test_r1_artifacts.py` |
| Parquet de R1 con el lector de R3 | 3 de 3 rechazados (`cell_id` ausente) | ídem (3 `xfail` estrictos) |
| DDL de R1 vs migraciones de R3 | R1 603 líneas normalizadas, R3 637; R1 ⊂ R3 salvo 4 puntos | `test_r3_schema_covers_everything_in_the_r1_ddl` |
| Script 92 de R1 sobre el esquema de R3 | `security_invoker` pasa a `NULL`; usuario sin parcelas ve **16 filas** ajenas (0 con la opción restaurada) | `test_r1_script_92_*`; SQL de demostración en la sesión |
| Rutas R4 vs R3 | 34/34 operaciones; 33 coinciden; difiere `/v1/healthz` | `pytest tests/contract/test_r4_artifacts.py` |
| Enums R4 vs especificación | 14/14 iguales | ídem |
| Cliente TS de R4 (`tsc -b`) | 0 errores contra su borrador; **358 → 302** contra el OpenAPI de R3 tras alinear rutas | ver §3 |
| Plantilla de informe de R4 | Renderiza; PDF A4 de 2 páginas; sin CSS incrustado el PDF pierde estilos en silencio (14 355 B vs 18 001 B) | `test_r4_template_pdf_keeps_its_stylesheet_and_a4_page_size` (Docker) |
| `gitleaks` | Sin hallazgos en R3, R1 (árbol e historial, 4 commits), R4 (código propio e historial, 1 commit) | imagen `zricethezav/gitleaks:v8.21.2` |

## 3. Comando del chequeo del cliente de R4 contra el OpenAPI de R3

Sin tocar `references/` (copia en un directorio temporal con `node_modules` enlazado):

```
copiar references/R4/apps/web + package.json  ->  <tmp>/apps/web ; enlazar node_modules
cd <tmp>/apps/web && set MILPA_OPENAPI_SPEC=<repo>\docs\openapi\openapi.json
node scripts/generate-types.mjs && ..\..\node_modules\.bin\tsc -b
```
Los 302 errores restantes: ~40 nombres de DTO que son `pending_r2` en R3 y diferencias de forma abiertas (C-03…C-06, C-18).

## 4. Pruebas creadas o ampliadas

`tests/contract/test_r1_artifacts.py` (CSV, Parquet, DDL, semillas, script 92, guardia), `tests/contract/test_r4_artifacts.py` (rutas, enums, DTO, plantilla, CSS, PDF), `tests/integration/test_hardening.py` (la API se niega a arrancar), `test_api_analysis.py` (forma `ProvenanceInfo`), `test_api_auth.py` (login para R4), bloque CSV de `apps/api/tests/test_storage_hashing_csv.py` reescrito.

## 5. No verificado

- Pruebas propias de R4 (Vitest, Playwright, axe): declaradas por R4, **no re-ejecutadas**.
- `registrar_procedencia.py`, `cargar_manifiesto.py`, ingesta con red (NASA): requieren BD/credenciales de R1; no ejecutados.
- Cualquier cálculo científico de R2 (no existe); ranking, heatmap, escenarios.
- Integración extremo a extremo (SPA de R4 contra la API en marcha con datos de R1).
- Equivalencia de `data_hash` entre R1 y R3 (C-16); GitHub Actions; `pre-commit`.
- `references/`: ningún archivo cambió de contenido; solo se refrescó el caché `.git/index` de ambos repos por comandos de lectura (`git log/status`).
