# Inventario documental (FASE 1 — descubrimiento)

Fecha: 2026-11-15 · Auditor: R3 (backend) · Alcance: todo lo que existe bajo la raíz del proyecto, incluida `references/`.
Método: listado recursivo, lectura de los documentos de reglas y ejecución/inspección directa de los artefactos (no solo de sus descripciones). Las cifras son las medidas en esta sesión.

## 0. Premisas del encargo que NO coinciden con lo que existe

| Premisa del encargo | Realidad verificada | Fuente |
|---|---|---|
| «R1, R3 y R4 son **estrategias** con cultivos, calendarios, variedades…» | **R1–R4 son paquetes de trabajo (equipos)**: R1 datos y evidencia, R2 motor científico, R3 backend y plataforma, R4 frontend y producto. Una *estrategia* es una entrada versionada del catálogo (`ref.strategy`: asociación, rotación, fecha de siembra, variedad) que consume el motor. | `README.md` §«Equipos» (líneas 2142-2145) y glosario (línea 89) |
| Existe una carpeta `backend/` en la raíz | **No existe.** El backend es `apps/api/` (R3). | `ls` raíz |
| Existe documentación/estrategias de R3 «dentro o fuera de `references/`» | R3 = `Especificacion_Tecnica_MILPA_R3.md` (1 421 líneas) + el código de `apps/api` de esta sesión. No hay otra carpeta ni documento de R3. | búsqueda en todo el árbol |
| Hay reglas agronómicas (Kc, fenología, calendarios, umbrales) que extraer de R1/R3/R4 | **Ninguno las contiene.** `references/Milpa-Resiliente-R1/catalogs/crops.yaml` declara todos esos parámetros `pending` (regla P9 «ningún valor agronómico inventado»); `regions/pilot_corredor_seco.yaml` deja zona y `agri_year_start` en `pending`. R4 no define ciencia (la UI no calcula). | ver `auditoria_R1.md` §3 |
| R2 «pendiente de implementación» | Confirmado: **no existe `packages/milpa_core`** ni nada de R2. | `Glob` |

**Consecuencia:** no se inventaron estrategias ni reglas agronómicas. La auditoría cubre lo que existe: la **compatibilidad de los entregables de R1 y R4 con el backend (R3) y con la especificación**, y el estado de las reglas científicas que la especificación asigna a R2. Si el solicitante se refería a otro conjunto de «estrategias» (p. ej. documentos con calendarios/variedades) no está en este árbol: **indique su ubicación**.

## 1. Jerarquía de fuentes aplicada (encargo §2)

1. `README.md` — *Especificación integral MILPA RESILIENTE 3.3* (2 472 líneas). **Documento oficial de reglas.**
2. `Especificacion_Tecnica_MILPA_R3.md` y `CLAUDE.md` (reglas del backend).
3. Entregables de R1 y R4 (`references/`) — documentación y código.
4. Implementación actual del backend (`apps/api`).
5. Suposiciones técnicas — solo si se declaran como tales (ADR).

> Nota de versión: `README.md` se modificó el 2026-11-15 00:40, **después** de la auditoría inicial de R3 (que registró 2 312 líneas; hoy son 2 472). No es posible determinar qué cambió; en particular, el apartado del CSV de suelo (§9) **ya fija el esquema** y R3 lo había tratado como «pendiente de R1» (ver `matriz_compatibilidad.md` C-15). Recomendación: tras cada cambio del README, repetir `tests/contract/` y esta auditoría.

## 2. Documentos de reglas (raíz)

| Archivo | Tamaño | Rol | Estado |
|---|---|---|---|
| `README.md` | 2 472 líneas | Especificación integral (producto, ciencia, datos, API, seguridad, pruebas, equipos) | Fuente oficial. Leídas por R3: §1-3, 7, 9, 10, 11.1-11.11, 13-16, 22-27 (sesión inicial: `docs/BACKEND_AUDIT.md` §1; esta sesión: §1-3, 9, 11, 16) |
| `Especificacion_Tecnica_MILPA_R3.md` | 1 421 líneas | Requisitos R3-F01…F22, ADR, pruebas del backend | Fuente oficial de R3 |
| `CLAUDE.md` | 73 líneas | Reglas de ingeniería del backend | Vigente |

Secciones del README **no** consolidadas en `reglas_consolidadas.md` (no relevantes para el backend o no leídas en detalle): §4-6 (contexto), §11.12-11.14 y §12 (escenarios, estabilidad, Soil VoI: solo metadatos de contrato), §17-20 (UI e informe en detalle), §28-31 (riesgos, DP). Si alguna es necesaria, se amplía.

## 3. `references/Milpa-Resiliente-R1` (R1 — Datos y evidencia)

Repositorio git propio (últimos commits «Add files via upload»). 22 archivos en la raíz + carpetas. **No es un paquete instalable** (`packages/milpa_etl` del §23 no existe): son scripts planos.

| Elemento | Archivos | Qué es |
|---|---|---|
| CLI/ETL | `milpa_r1.py` (56 KB), `imerg_r1.py` (48 KB) | Ingesta POWER/IMERG, QC, ET0 FAO-56, Pef por decena, cobertura, suelo CSV, demo sintética, `selftest` |
| Carga a BD | `registrar_zona.py`, `cargar_manifiesto.py`, `registrar_procedencia.py`, `ingestar_suelo_db.py`, `seed_catalogo.py` | Escriben en PostgreSQL **directamente** (psycopg, `DATABASE_URL`) |
| Diagnóstico | `diagnostico_lluvia.py`, `verificar_power_raw.py`, `imerg_probe.py`, `fetch_dem.py`, `calidad.py` | Solo lectura / descarga |
| SQL | `sql/000_init.sql`, `01_auth`…`10_report`, `90_seed`, `91_seed_soil`, `92_soil_fixture_provenance`, `93_seed_imerg` (15) | DDL del README §13 + semillas |
| Catálogos | `catalogs/crops.yaml`, `catalogs/evidence_rules.yaml`, `regions/pilot_corredor_seco.yaml` | **Todo `pending`/«propuesta»** (ver arriba) |
| Datos | `data/curated/chiquimula_prueba/{daily,dekad,coverage}.parquet`, `curated_meta.json`, `validation_report.json`, `precip_validation.json`; `data/curated/soil/P-014.parquet` | Serie 2001-2025 (9 131 días) de una zona de **prueba** (polígono aproximado, no oficial) |
| CSV de suelo | `suelo.csv`, `suelo_prueba.csv`, `suelo_invalido.csv`, `suelo_invalido_p014.csv` | Ejemplos válidos e inválidos |
| Otros | `README.md`, `requirements.txt`, `docker-compose.yml`, `env.example`, `zona_chiquimula_prueba.geojson` | — |

## 4. `references/R4` (R4 — Frontend y producto)

Repositorio git propio (commit `ce227a3` + cambios sin confirmar). Monorepo npm; `node_modules` presente.

| Elemento | Archivos | Qué es |
|---|---|---|
| Frontend | `apps/web/src/**` (TSX/TS), `e2e/`, config Vite/Vitest/Playwright | 4 pantallas, componentes de procedencia, mock con fixture sintético rotulado |
| Contrato | `contracts/openapi.v0.draft.yaml` (55 KB, 34 operaciones, 81 esquemas) | **Borrador local derivado**; no es el contrato oficial |
| Tipos | `apps/web/src/api/types.gen.ts` (generado) | Desde el borrador |
| Plantilla de informe | `apps/api/templates/{report_es.html.j2, report_es_en.html.j2, report.css}` | Jinja2 + CSS de impresión |
| Documentos | `docs/{CONTRACT_RECONCILIATION, INTEGRATION_HANDOFF, IMPLEMENTATION_STATUS, PRODUCT_TRACEABILITY, REPORT_TEMPLATE, DESIGN_SYSTEM, DEMO_SCRIPT, REPOSITORY_AUDIT, USABILITY_PLAN, USABILITY_REPORT}.md` | Estado, reconciliación SPEC-01…06, trazabilidad UX↔F↔API |
| Pruebas | `tests/acceptance/` (T-A·A–J, Playwright), `apps/web/src/**/*.test.ts(x)` | Contra fixture sintético |
| Herramientas de agente | `.claude/skills/**` (guías y scripts de diseño, varios MB) | **No son producto**; se ignoran |

## 5. R3 (este backend)

`apps/api/` (FastAPI, 13 migraciones Alembic, 34 operaciones), `testkit/`, `tests/`, `docs/` (API, DATABASE, SECURITY, PRIVACY, JOBS, REPORTS, REPRODUCIBILITY, TESTING, DEPLOYMENT, 16 ADR, `integration/`, `openapi/`). Estado y límites: `docs/BACKEND_AUDIT.md`, `docs/integration/INTEGRATION_STATUS.md`.

## 6. Lo que falta (y quién debe entregarlo)

| Ausente | Dueño | Efecto |
|---|---|---|
| `packages/milpa_core` (motor, enums, DTO de resultado, reglas de evidencia, `ReportModel`, errores tipados) | R2 | Endpoints de análisis → 503 `DEPENDENCY_NOT_INTEGRATED`; no hay ranking/heatmap/escenarios reales |
| `data/demo/` y `EXPECTED.json` | R1/R2 | `make demo` y `make reproduce` salen con código 2 |
| Catálogo de estrategias, cultivos, Kc, fenología, umbrales con cita; `region pack` con zona y `agri_year_start` | R1 (con asesor) | Imposible definir ni validar estrategias agronómicas (P9) |
| OpenAPI **oficial** de R3 revisado por R2/R4 | R3+R2+R4 | R4 trabaja contra su propio borrador |
| `docs/templates/soil.csv` (citado en README §«Demostración») | R1/R3 | Se usa `suelo.csv` de R1 como ejemplo |
| Decisiones DP-01…DP-17 | Equipo/asesor | Ver `plan_integracion.md` |
