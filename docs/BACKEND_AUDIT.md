# Auditoría técnica inicial del backend (R3)

**Fecha:** 2026-11-14 · **Alcance:** R3 — Backend y plataforma · **Estado de este documento:** vivo; la sección 9 registra cambios posteriores a la auditoría inicial.

## 1. Estado del repositorio al iniciar

| Elemento | Hallazgo |
|---|---|
| Git | El directorio **no es un repositorio Git** (sin `.git`). No hay historial ni cambios sin confirmar que proteger. Se recomienda `git init` y primer commit por el equipo; R3 no lo ejecutó. |
| Contenido | Solo 3 archivos: `CLAUDE.md` (nótese: minúsculas; los documentos lo citan como `CLAUDE.MD`), `Especificacion_Tecnica_MILPA_R3.md` (1422 líneas) y `README.md` (2312 líneas, es la **especificación integral MILPA RESILIENTE 3.3**, no un README de uso). |
| Código, `pyproject.toml`, `uv.lock`, CI, Docker, migraciones | **No existían.** Proyecto desde cero (greenfield). |
| `packages/milpa_core` (R2), `packages/milpa_etl` (R1), `apps/web` (R4), `regions/`, `catalogs/`, `data/` | **No existen.** Ningún entregable de R1/R2/R4 está disponible. |

Se leyeron completos `CLAUDE.md` y la especificación R3, y las secciones del README integral relevantes para R3 (§7 stack, §10 `milpa_core`, §13 modelo de datos, §14 ER, §15 DTOs, §16 API, §22 seguridad, §23 estructura, §24 pruebas, §25 reproducibilidad, §26–27 equipos/hitos).

## 2. Entorno de trabajo encontrado

| Herramienta | Estado | Acción |
|---|---|---|
| Python | 3.10 y 3.13 instalados; **3.12 ausente** | `uv python install 3.12` → CPython 3.12.16 (workspace fijado en `.python-version`). |
| uv | Ausente | Instalado con `pip --user` (uv 0.13.8). |
| Docker | CLI presente, **daemon apagado** | Se inició Docker Desktop; se descargó `postgis/postgis:16-3.4` (PostgreSQL 16.4, PostGIS 3.4.3). |
| make / psql | Ausentes en el host Windows | El `Makefile` se valida con `make -n` dentro de un contenedor; `psql` se usa dentro del contenedor `db`. |
| WeasyPrint nativo | **No carga en Windows** (`libgobject-2.0-0` ausente) | Las pruebas PDF se ejecutan dentro de la imagen Docker (Pango incluida). En el host se marcan `pdf` y se omiten con motivo explícito. |

## 3. Arquitectura objetivo (de las fuentes)

Monolito modular: `apps/api` (FastAPI) + PostgreSQL/PostGIS; trabajos con `engine.job` + `concurrent.futures`; Parquet bajo `DATA_DIR`; `milpa_core` solo vía puerto/adaptador; PDF con Jinja2 + WeasyPrint. Dos contenedores: `db` y `app`. Sin Redis/Celery/ARQ/Dask/MinIO/Kubernetes.

## 4. Requisitos BE-01…BE-11 y estado de partida

| ID | Requisito | Dependencias externas | Estado inicial |
|---|---|---|---|
| BE-01 | Monorepo, CI, lint, tipos | — | no existía |
| BE-02 | OpenAPI v0, mock, tipos TS | DTOs R2 (parcial), consumo R4 | no existía |
| BE-03 | Auth, RBAC, RLS, consentimiento, borrado | Reglas de evidencia (R2) para persistir suelo | no existía |
| BE-04 | Trabajos / `engine.job` | Handlers científicos dependen de R1/R2 | no existía |
| BE-05 | Zonas, parcelas, suelo, CSV | Esquema CSV v1 y catálogo `ref.soil_property` (R1) | no existía |
| BE-06 | Endpoints de análisis | `milpa_core` (R2), Parquet (R1) | no existía |
| BE-07 | Informe PDF | `ReportModel` (R2), plantilla final (R4) | no existía |
| BE-08 | Pruebas de seguridad/privacidad | — | no existía |
| BE-09 | Docker, demo, Makefile | `data/demo/` (R1) | no existía |
| BE-10 | Reproducibilidad | `EXPECTED.json`, motor, datos (R1/R2) | no existía |
| BE-11 | Benchmarks | Motor y datos reales para ranking/heatmap | no existía |

## 5. Puntos de integración pendientes (resumen; detalle en `docs/integration/`)

- **R1:** esquema real de Parquet y manifiesto, `EXPECTED.json`, catálogos `ref.*`, esquema CSV de suelo v1, `ingestion_run`. R3 no implementa ingesta.
- **R2:** `milpa_core` (fachada de 5 funciones, `enums`, `Indicator`/`ProvenanceInfo`, DTOs de resultado, `ReportModel`, errores tipados, reglas de evidencia).
- **R4:** consumo de OpenAPI, plantilla final del informe, textos.

## 6. Conflictos y decisiones que requieren ADR

| # | Conflicto / hueco | Resolución propuesta | ADR |
|---|---|---|---|
| C1 | README integral usa `docs/adr/`; la especificación R3 y el encargo usan `docs/decisions/` | Se usa `docs/decisions/` (spec R3 §24 tiene precedencia más específica para R3). Pendiente de confirmación del equipo. | ADR-001 |
| C2 | Propiedad de migraciones: R1 es dueño de `prov/ref/geo/soil/econ`; R3 necesita una única cadena Alembic y esas tablas por FK | **Una sola cadena Alembic** en `apps/api/migrations`. Revisiones de `prov/ref/geo/soil/econ` se escriben desde el DDL **[Propuesto]** del README §13, marcadas `OWNER: R1 / provisional`. R1 asume su contenido por PR sin reordenar revisiones. **Pendiente de aprobación.** | ADR-003 |
| C3 | Orden `auth→prov→ref→geo→…` pero `ref.strategy.region_id → geo.region` (FK hacia adelante) | `ref.strategy` se crea sin esa FK; la FK se agrega en la revisión `geo`. | ADR-003 |
| C4 | `engine.job.kind` solo admite 4 tipos, pero el borrado de parcela y la limpieza por retirada de consentimiento deben ejecutarse como trabajo | Se añaden `parcel_delete` y `consent_purge` al CHECK (extensión R3, **pendiente de aprobación**). | ADR-007 |
| C5 | `prov.indicator_provenance` exige `evidence_level` para todo menos `desconocido`, pero el nivel A/B/C lo decide R2 | R3 **no asigna evidencia**: la persistencia de mediciones/declaraciones de suelo pasa por un puerto `EvidencePort`; sin R2 devuelve 503 `DEPENDENCY_NOT_INTEGRATED`. | ADR-009 |
| C6 | Enums científicos: fuente canónica `milpa_core.enums` (no existe) | Espejo **provisional** aislado (`api.contracts.provisional_enums`) que se sustituye por import de `milpa_core.enums` cuando exista; prueba de paridad Python↔SQL↔OpenAPI. | ADR-009/010 |
| C7 | Contratos sin definir: registro de usuarios, alta de consentimiento/asignación, payloads de `POST /zones`, `/parcels`, `/zones/{id}/runs`, `/reports`, CSV de suelo | Contratos **provisionales** etiquetados (`x-contract-status`) o sin endpoint (registro, consentimiento) hasta aprobación. | ADR-010 |
| C8 | Admin puede borrar parcela "según política aprobada"; la política de acceso excepcional no existe | `DELETE /parcels/{id}` solo para el dueño; la ruta admin queda bloqueada hasta aprobar la política (DP-13). | ADR-015 |

## 7. Riesgos

RLS mal configurada; trabajos huérfanos tras reinicio; WeasyPrint (nativo) en la imagen; deriva de enums; DTOs de R2 incompatibles; migraciones duplicadas entre R1 y R3; Parquet ausente o con esquema no confirmado; mocks que lleguen a producción; borrado incompleto; datos personales en logs/PDF/demo. Cada uno tiene control y prueba asignados en `docs/SECURITY.md` y `docs/TESTING.md`.

## 8. Plan de implementación (orden ejecutado)

Fase 0 (auditoría, ADR, workspace, CI, OpenAPI v0) → S1 (Docker/DB/FastAPI/Alembic/jobs/health) → S2 (JWT/Argon2id/RBAC/RLS/consentimiento/zonas/parcelas) → S3 (adaptadores y endpoints de análisis) → S4 (PDF) → S5 (escenarios, VoI, CSV, suelo) → S6 (seguridad, reproducibilidad, benchmarks, CI, auditoría final).

## 9. Registro de cambios posteriores (2026-11-15)

**Implementado tras la auditoría:** monorepo uv + Python 3.12, FastAPI modular, PostgreSQL 16/PostGIS con cadena Alembic única (13 revisiones), RLS con rol de aplicación sin BYPASSRLS, JWT + Argon2id + bloqueo progresivo, consentimiento y borrado, trabajos con `ProcessPoolExecutor`, 34 operaciones HTTP (las de la especificación), adaptadores R1/R2 `NotIntegrated`, CSV de suelo, servicio PDF con WeasyPrint restringido, reproducibilidad (hashes/manifiestos/`reproduce`), mock, benchmarks, Docker (2 servicios), CI, 16 ADR y documentación.

**Problemas hallados *por las propias pruebas* durante el desarrollo (y corregidos):**
1. El CSS de impresión salía escapado por el autoescape de Jinja2 (PDF sin estilos) → se incrusta como contenido de confianza.
2. OpenAPI documentaba el 422 de FastAPI y `application/json` para errores que se sirven como `application/problem+json` → corregido y verificado con Schemathesis.
3. Parámetros enteros sin cota provocaban `500` por desborde de `int4` (`/versions/2147483648`) → acotados.
4. Los registros de `httpx` incluían la URL con *query string* (posible fuga) → redacción de *query strings* y niveles de librerías HTTP.
5. El handler de logs quedaba ligado al `stdout` del momento de su creación → ahora resuelve `sys.stdout` en cada emisión (y una prueba de privacidad vacía fue reemplazada por otra con aserción de no-vacío).
6. Mapeo ORM de `adaptation_t` como texto rompía las consultas de escenarios → enum mapeado.
7. Las políticas RLS por fila hacían `count(*)` de 10 000 filas en ~4,8 s (benchmark) → conjuntos visibles evaluados una vez (~23 ms) sin cambiar el comportamiento de seguridad.
8. Al verificar con `docker compose up` real aparecieron dos fallos que ninguna prueba previa cubría: (a) `chmod` sobre todo `initdb.d` volvía ejecutable el script de la imagen base de PostGIS y abortaba la inicialización (el rol de aplicación no se creaba); (b) `CORS_ORIGINS` vacío (valor por defecto de `.env.example`) impedía arrancar. Corregidos, con prueba de regresión para (b).
9. `opentelemetry-api` entra como dependencia **transitiva de FastAPI** (descartado en el MVP): se permite solo eso (sin SDK/exportadores) y queda vigilado por prueba.

**Incidente de entorno:** el disco C: llegó a 0,4 GB libres y Docker Desktop se colgó (volumen `docker_data.vhdx` «ya conectado»). Se limpió únicamente la caché de `uv` (creada por esta sesión), se apagó WSL y se relanzó Docker Desktop (que había iniciado esta sesión). Los contenedores `erp-system-*` de otro proyecto se reiniciaron solos con su política `restart`; no se tocaron.

**Sigue sin hacerse (por depender de otros roles o de decisiones):** ver `docs/integration/INTEGRATION_STATUS.md` y la lista de pendientes del informe final.

## 10. Auditoría de integración con R1 y R4 (2026-11-15, posterior)

Al aparecer `references/` (entregables reales de R1 y R4) se hizo una auditoría de compatibilidad ejecutable; los documentos están en `docs/auditoria/` (inventario, reglas consolidadas, auditorías R1/R3/R4, matrices de compatibilidad y trazabilidad, plan de integración e informe de validación).

**Correcciones a lo afirmado antes en este documento y en el informe final inicial:**
1. *«El esquema CSV de suelo v1 está pendiente de R1»* era **incorrecto**: el README §9 lo define y R1 lo cumple. R3 había inventado un contrato propio; se reemplazó por `SOIL_CSV_V1` (ADR-017).
2. `GET /provenance/{ip_id}` devolvía nombres de columnas de BD en lugar del `ProvenanceInfo` del §15; corregido.
3. Las plantillas de ruta se habían renombrado (`{zone_id}`…) en lugar de usar las de la especificación (`{id}`…); corregido (rompía clientes tipados).
4. Se registra que `README.md` cambió el 2026-11-15 00:40 (2 312 → 2 472 líneas) después de la auditoría inicial; no es posible saber si el apartado del CSV ya existía.

**Hallazgo de seguridad (ajeno a R3, con defensa añadida):** `sql/92_soil_fixture_provenance.sql` de R1 elimina `security_invoker` de `soil.property_status` y permite leer filas de parcelas ajenas. R3 ahora **no arranca** si ocurre (`api.db.invariants`).

**Premisa del encargo no confirmada:** R1/R3/R4 no son «estrategias» agronómicas sino paquetes de trabajo; no existen parámetros agronómicos en ningún entregable (todo `pending`) ni `milpa_core` (R2). No se inventó ninguno.

## 11. Integración de R1 y R4 en la raíz (2026-11-15, ADR-018)

Por instrucción del solicitante, lo entregado por R1 y R4 (`references/`, que queda intacto) se integró en este repositorio siguiendo el README §23: `packages/milpa_etl`, `catalogs/`, `regions/`, `data/curated`, `data/demo`, `apps/web`, `tests/acceptance`, `docs/r4/`. R2 **no** se creó: lo entregará su responsable; el adaptador y los DTO pendientes quedan listos.

Resultados verificados y límites: `docs/TESTING.md` §7 y `docs/integration/INTEGRATION_STATUS.md`. Hallazgos nuevos de esta etapa:
1. Los dos archivos de validación de R1 (`precip_validation.json` y `validation_report.json`) dan estadísticos distintos para IMERG vs POWER (SV-06).
2. R1 no entrega `data/manifest/ingestions.jsonl` ni los JSON crudos: `register provenance` no puede ejecutarse con lo que hay en el repositorio (no se reconstruye linaje).
3. `seed_catalogo.py` y `fetch_dem.py` de R1 usaban `psycopg2` aunque su `requirements.txt` declaraba `psycopg` 3: portados.
4. Playwright de R4 no distinguía `references/` de la raíz (cargaba dos copias de `@playwright/test`): `testIgnore` corregido.

**Verificación final:** suite completa en Docker 410 aprobadas, 2 omitidas, 1 `xfail`, 0 fallos (ver `docs/TESTING.md` §7). **No hecho / pendiente:** R2 (`milpa_core`); ingesta real con red y token NASA; Playwright contra la API real; etapa de build del frontend en la imagen Docker; ejecución de GitHub Actions; aprobación de ADR-003, 007, 009, 010, 015, 016, 017 y 018.
5. `build-demo` de R1 produce `data_hash` distintos en Windows y Linux (ruido de último bit, ≤ 4,6·10⁻¹⁶): `make reproduce` aplica una tolerancia numérica provisional (ADR-018 §10, SV-07).

> **Traspaso de contexto completo (tareas pendientes, errores, correcciones y pruebas sin verificar): `docs/HANDOFF.md`.**
