# TRASPASO PARA EL SIGUIENTE AGENTE — MILPA RESILIENTE (2026-11-16)

Lee primero: `CLAUDE.md`, `NEXT_STEPS.md`, `docs/FINAL_PROJECT_AUDIT.md`, `Especificacion_Tecnica_MILPA_R3.md`.
Este archivo cubre **solo** la tarea en curso: *revisión integral de la página y del flujo de informes, sin Docker*.
El resto del proyecto (R1–R4, demo sin login, hub MVP) está descrito en `NEXT_STEPS.md`.

## 0. Reglas que el usuario fijó (no las rompas)
- La app **debe funcionar sin Docker**: no introducir Docker como requisito, no pedir instalarlo, no romper `scripts/start_local.ps1`.
- No copiar encima ni revertir los muchos cambios locales del usuario; no borrar los activos de `references/`.
- Sin parcelas/polígonos sintéticos; las coordenadas precisas nunca se persisten ni se loguean (solo celda generalizada ≥ 1 km).
- Un informe `public` no puede llevar id/nombre de parcela, coordenadas precisas, correos ni datos personales.
- No inventar datos, umbrales, pH, rendimientos, precios, profundidades de raíz, AWC, fechas exactas; nunca `null → 0`; nunca mock como real.
- No commitear ni hacer push salvo que el usuario lo pida (el remoto `origin` tiene historia no relacionada; nunca force-push).
- Nada de infraestructura nueva sin ADR; los endpoints nuevos exigen ADR + actualizar los tests de contrato (hoy: 35 operaciones).

## 1. Qué está HECHO y VERIFICADO (ejecutado)

### Bloque 4 — PDF sin Docker (ReportLab, Python puro)
- `apps/api/src/api/reports/pdf.py` (nuevo): `render_pdf(ReportInput) -> bytes`. A4, bilingüe (`es` / `es+en`), pie «Página X de Y», tablas con cabecera repetida y pesos de columna, URLs clicables, fuentes Vera incluidas en ReportLab (mono = Courier), determinista (`invariant=1`), escaneo de privacidad previo para `public`.
- `reports/contract.py`: `ReportTable` (+ `weights`), `ReportSection.table`, `ReportSection.items_en` (paralelo a `items`).
- `reports/service.py::generate` usa `render_pdf`; `jobs/handlers/reports.py` ya no admite «informe sin PDF».
- `apps/api/pyproject.toml`: `reportlab>=4.2,<5` como dependencia; `weasyprint` pasó a extra opcional `html-pdf`. `uv.lock` regenerado (`uv lock`, uv 0.13.8 instalado fuera del repo; **no** se ejecutó `uv sync`).
- `reports/from_engine.py` reescrito: secciones bilingües con tablas (cobertura IMERG por año con **2025 parcial: 273/365 = 74,8 %**, estrategias y ciclos, riesgo con unidades, ranking por criterio, criterios efectivamente usados con pesos pedidos/aplicados y motivo, escenarios sintéticos calculados + comparación, procedencia por indicador con tipo de evidencia, decisiones pendientes, datos faltantes). Lo que el motor no registra se dice («el motor no registra… periodo, fecha de descarga…»), no se rellena.
- `reports/context.py` (nuevo): lee `coverage.parquet`/`curated_meta.json` y los escenarios persistidos.
- `security/privacy.py`: bug real corregido — un DOI (`10.25966/564j-4331`) se detectaba como coordenada y **todo informe público real fallaba**. Ahora `DOI_RE` se excluye del escaneo (test en `test_config_security.py`).
- Verificado de extremo a extremo con la API real: sesión demo → `POST /v1/reports` → job → `GET /v1/reports/{id}` → `GET /v1/reports/{id}/pdf` (200, SHA-256 coincide con el registrado). PDF público e interno generados desde el run real `16e09331-37c8-4fa8-8859-708e3bce8a06` (zona `camotan_jocotan`, 2001–2025): 9 páginas, inspeccionadas como imagen.
- Web: `apps/web/src/api/pdf-download.ts` (descarga **autenticada**: un `<a href>` no lleva el token) + verificación SHA-256 en el navegador; `components/report/ReportSection.tsx` (tablas, `items_en`); `ReportScreen.tsx` usa ambos. Probado en el navegador: generar → ver 14 secciones/9 tablas → descargar → «SHA-256 coincide».
- Web: `src/api/client.ts` + `public-access.ts`: si el servidor rechaza el token demo (401, p. ej. tras reiniciar con otra clave), se renueva en silencio y se reintenta una vez. Probado en el navegador.

### Bloque 3 (parcial) — frontera municipal y mapa
- `apps/api/src/api/geo/boundary.py` (nuevo): valida el GeoJSON (FeatureCollection de 1 municipio, CRS EPSG:4326, anillos cerrados, dentro de Guatemala, sin autointersección) y calcula SHA-256. `python -m api.cli check-boundary` lo imprime (Jocotán, Chiquimula, COD_MUN 2004, 320 vértices, sha256 `07222a54…2be2`; PostGIS confirma polígono válido de ~251 km²).
- `Settings.municipal_boundary_file` (por defecto `None` = solo regla de zona). Con ruta configurada, `POST /v1/parcels` rechaza (422, sin repetir la coordenada) ubicaciones fuera del municipio con `ST_Covers` en PostGIS; archivo inutilizable → 503 (falla cerrado). Cambios en `repositories/farms.py::covered_by_geojson` y `services/parcels.py::_require_inside_municipality`.
- `apps/web/src/lib/boundary.ts` (+ test): mismo GeoJSON empaquetado, punto-en-polígono con huecos/multipolígonos e inclusivo en el borde (igual que el servidor).
- `ZoneMap.tsx` reescrito: i18n es/en, leyenda (límite, celdas climáticas como *capa de contexto*, zona de análisis, selección), aviso si fallan las teselas, formulario de coordenadas (alternativa accesible al clic) con validación, botones «Centrar»/«Borrar», mensaje «dentro de Jocotán / dentro o fuera de la celda climática analizada», nota «no se guarda ni se crea parcela». `adapters.ts` ahora entrega `context.area` (geometría de la zona) que el mapa dibuja.

### Resultados de pruebas (todos ejecutados en esta sesión)
| Qué | Resultado |
|---|---|
| `apps/api/tests/test_reports_pdf_reportlab.py` + `test_report_from_engine.py` | 27 passed |
| `test_reports.py`, `tests/integration/test_reports_pdf.py`, `tests/contract/test_r4_artifacts.py` | 44 passed, 6 skipped (solo la ruta opcional WeasyPrint/Pango) |
| `tests/integration/test_municipal_boundary.py` + `test_api_parcels.py` + `test_rls.py` | 53 passed |
| `apps/api/tests/test_config_security.py` | 27 passed |
| vitest: `ReportSection` 5, `boundary` 7, `ZoneMap` 8 (react-leaflet *stubbed*: jsdom no tiene SVG) | passed (cada uno por separado); la corrida completa de 36 fue antes de ZoneMap/boundary |
| `tsc -b`, `eslint src`, `vite build` | limpios / OK en la última corrida |

## 2. Qué NO está verificado o quedó roto (haz esto primero)
1. **Lint pendiente (2 errores)**: `ruff check apps/api testkit tests --fix` → `services/parcels.py` (I001 orden de imports) y `apps/api/tests/test_report_from_engine.py:104` (RUF003, un `–` en un comentario; usa `-`). Luego `ruff format` y `mypy` (se editó `cli.py` después de la última corrida de mypy).
2. **Suite completa de Python no ejecutada tras los cambios**: `.venv/Scripts/python.exe -m pytest apps/api/tests tests -m "not slow" -q`.
3. **vitest completo y `npm run test:copy`** no ejecutados tras ZoneMap/boundary: `cd apps/web && npx vitest run && node --test src/lint/copy-linter.test.ts`. Hay un linter de textos (`copy-linter`): puede objetar cadenas nuevas.
4. **El nuevo `ZoneMap` no se vio en el navegador** (el `dist` sí se reconstruyó). Abrir `/my-zone?runId=16e09331-37c8-4fa8-8859-708e3bce8a06&zoneId=6d7331ed-d1cd-496b-bf7d-c8aaebc97a35`, probar clic, coordenadas, móvil (≤ 560 px), y revisar contraste. La versión previa sí cargó 15 teselas OSM.
5. Playwright (`apps/web`, `npm run test:e2e`) no se ejecutó; el E2E local de la sesión fue por script HTTP + navegador del panel.
6. Hay un servidor `uvicorn` que dejé corriendo en `127.0.0.1:8000` (clave JWT fija de desarrollo). Para detenerlo: `netstat -ano | findstr :8000` y `taskkill /PID <pid> /F`.

## 3. Lo que falta (por bloque del encargo)

### Bloque 4 — terminar «sin Docker» (código y docs)
- `apps/api/src/api/cli.py::cmd_report_sample` y `apps/api/src/api/bench/runner.py` (~l.426) todavía usan `html_to_pdf(render_html(...))` (WeasyPrint). Cambiar a `render_pdf`.
- Actualizar textos que dicen «PDF solo en Docker/Pango»: `README.md` (§7, §8, §11), `NEXT_STEPS.md` (ítem 5 y «Arranque rápido»), `docs/DEPLOYMENT.md`, `docs/REPORTS.md`, `docs/TESTING.md`, `docs/API.md`, `docs/r4/REPORT_TEMPLATE.md`, `infra/Dockerfile.app` (ya no necesita Pango salvo extra `html-pdf`), `.github/workflows/ci.yml`, `Makefile`, `infra/scripts/test-docker.sh`, `tests/contract/test_boundaries.py` (menciona weasyprint), marcador `pdf` en `pyproject.toml`, `logging_config.py`.
- ADR nuevos en `docs/decisions/`: **ADR-021** (ReportLab como motor PDF soportado; WeasyPrint opcional) y **ADR-022** (guardia de frontera municipal / selección de ubicación). `docs/decisions/README.md` índice.
- `scripts/start_local.ps1` aún ejecuta `docker start milpa-test-db`: hacerlo tolerante (si no hay Docker, usar `DATABASE_URL` del entorno). Documentar que sin Docker hace falta **PostgreSQL 16 + PostGIS** local (la app los necesita; eso no es el PDF).
- Añadir `MUNICIPAL_BOUNDARY_FILE=./regions/jocotan_chiquimula_boundary.geojson` a `.env.example`, `scripts/start_local.ps1` y docker-compose (hoy la regla está apagada por defecto).
- Test que ejecute la descarga del PDF desde la API sin Pango (hay uno de integración; falta correrlo en un entorno sin WeasyPrint importable, p. ej. con `PYTHONPATH` sin la rueda — ya hay un test que simula la ausencia).

### Bloque 3 — mapa y selección
- Documento `docs/MAP_AND_LOCATION.md`: metadatos de la frontera (archivo, CRS, COD_MUN/COD_DEPTO, vértices, sha256, `check-boundary`), **procedencia/atribución del polígono NO consta en el archivo** (preguntar al usuario quién lo proveyó; no inventar SEGEPLAN/IGN), política de uso de teselas OSM (uso ligero con atribución; configurable por `VITE_MAP_TILE_URL`/`VITE_MAP_ATTRIBUTION`; sin token), por qué no hay buscador de localidades (no hay fuente fiable ni de licencia clara; Nominatim restringe el autocompletado).
- La zona `camotan_jocotan` solo tiene registrada la celda **POWER** en `geo.climate_cell`; la celda **IMERG 0,1°** (lon −89.4…−89.3, lat 14.8…14.9; es el polígono de la propia zona) no está registrada como celda. Hoy el mapa la dibuja como «zona de análisis». Decidir si registrarla en `geo.climate_cell` (ETL R1).
- Nombre legible de zona («Corredor Seco — Jocotán, Chiquimula») en vez de `camotan_jocotan`: no existe campo de nombre para mostrar; añadirlo vía región/YAML o tabla (sin romper contratos) y usarlo en informe, MVP y mapa.
- La demo pública no puede crear parcelas (alcance en `security/demo.py`); por eso el mapa es solo comprobación visual. Si se quiere persistir la selección para roles con permiso, usar el `POST /v1/parcels` existente (ya validado en servidor).

### Bloque 1 — auditoría de páginas y datos (casi sin empezar)
- Recorrer `/`, `/demo`, `/mvp`, `/my-zone`, `/calendar`, `/rotations`, `/plants`, `/report`, suelo/parcelas, y trazar cada indicador API → adapter → componente. Corregir los «No evidence level / unknown / Prov. / Not available» de las celdas del heatmap y del panel «What the engine says» (capturas del usuario), UUID crudos (moverlos a un bloque técnico plegable con nombres legibles), tablas vacías y errores genéricos.
- Mostrar en la web (no solo en el PDF) fuente, institución, producto/versión, periodo, resolución, método, cobertura, fecha de descarga, supuestos y límites por indicador; separar visualmente observado / satélite-reanálisis / derivado-modelado / declarado / hipotético / no disponible; **marcar 2025 como parcial** con cobertura y denominador (los datos están en `/v1/zones/{id}/data-quality` → `coverage`, variable `precip_imerg_mm`, año 2025: 273 de 365).
- Heatmap/matriz legible en escritorio y móvil (sin años ni cifras cortadas; la evidencia no debe colapsar celdas en tarjetas angostas).
- Migrar a i18n el inglés/español fijo en `MvpScreen`, `DemoScreen`, `PlantsScreen`, `HomeScreen`, `SourceStatus`, `StrategyCompare`, `ScenarioLauncher`, etc., con paridad es/en.

### Bloque 2 — datos y referencias R1/R2 (no empezado)
- Inspeccionar `references/Milpa-Resiliente-R1` y `references/R2` y los catálogos importados (`catalogs/r2/*.yaml`, `regions/r2/*.yaml`) sin duplicar ni sobrescribir.
- Completar calendarios/variedades/Kc/duración de etapas con fuentes públicas **primarias**, registrando URL/DOI, título, institución, fecha/edición, cultivo/variedad, ámbito espacial, unidad y limitaciones en catálogos versionados: MAGA «Épocas de siembra y cosecha» (https://www.maga.gob.gt/download/epocas-siembra-cosecha-agricolas-guatemala.pdf), SCEP-MAGA Jocotán (https://scep.gob.gt/wp-content/uploads/2023/11/Jocotan.pdf), boletín agroclimático Chiquimula (https://www.maga.gob.gt/download/7boletin3-chiquimula.pdf), FAO Kc (https://www.fao.org/4/s2022e/s2022e07.htm). Estado `regional_reference`; salida provisional; nunca extrapolar calendarios nacionales a validación de parcela.
- Validación de esquema de catálogos + prueba que impida promover parámetros sin cita o fuera de alcance. Revisar manifiestos POWER/IMERG (hashes, unidades, periodo, aviso de no validación con estación local).
- Verificar la cita del producto IMERG: el repo registra «GPM IMERG daily GIS product (DOI 10.25966/564j-4331)»; no la verifiqué contra la fuente. La referencia FAO-56 va sin URL a propósito.

### Bloque 5 — cierre
- Correr TODO (sección 2), Playwright si es viable, `npm run build` (incluye `types:generate`; el contrato OpenAPI no cambió en esta tanda), y actualizar `NEXT_STEPS.md` + `docs/FINAL_PROJECT_AUDIT.md` con estado verificado/no verificado y comandos reales.
- Resumen final al usuario: cambios por archivo, fuentes, datos aún no validados, y los comandos de abajo.

## 4. Comandos (Windows, sin Docker para el PDF)
Entorno: `.venv` ya existe (Python 3.12). Base de datos: PostgreSQL 16 + PostGIS (hoy el contenedor `milpa-test-db` en `127.0.0.1:55432`, base `milpa_dev`, ya migrada y con zona/catálogo/usuario demo).

```bash
# API (desde la raíz; valores SOLO de desarrollo local)
export DATABASE_URL="postgresql+psycopg://milpa_app:app_test_only@127.0.0.1:55432/milpa_dev"
export JWT_SECRET="local-dev-secret-0123456789abcdef0123456789abcdef" DATA_DIR=./data MILPA_MODE=sandbox
export DEMO_PUBLIC_ACCESS=true RATE_LIMIT_PER_MIN=1200 PYTHONUTF8=1
.venv/Scripts/python.exe -m uvicorn --factory api.main:create_app --host 127.0.0.1 --port 8000
# o: powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1   (hoy llama a docker start; ver §3)

# Frontend (sirve apps/web/dist desde la API)
cd apps/web && npx vite build

# Generar y descargar un PDF (informe público; sesión demo, sin login)
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/v1/auth/demo-session | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
JOB=$(curl -s -X POST http://127.0.0.1:8000/v1/reports -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: k$(date +%s)" -H "Content-Type: application/json" -d '{"run_id":"16e09331-37c8-4fa8-8859-708e3bce8a06","locale":"es+en","privacy_level":"public"}')
# consultar GET /v1/jobs/<job_id> hasta status=ok → result.report_id
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/v1/reports/<report_id>/pdf -o informe.pdf

# Frontera municipal
.venv/Scripts/python.exe -m api.cli check-boundary

# Pruebas
.venv/Scripts/python.exe -m pytest apps/api/tests/test_reports_pdf_reportlab.py apps/api/tests/test_report_from_engine.py -q
.venv/Scripts/python.exe -m pytest tests/integration/test_municipal_boundary.py tests/integration/test_reports_pdf.py -q
cd apps/web && npx vitest run
```
En la UI: `/report?runId=<run>` → «Generar informe» → «Descargar PDF (A4)».

## 5. Trampas del entorno (te ahorrarán tiempo)
- **Escapes en herramientas**: los heredocs de Bash con `\\u00d7`, `\b` o `\\n` llegan alterados (backspace/saltos de línea reales). Para escribir `\u…`, `\b` o `\n` en archivos usa un script `.py` con `chr(92)`. Verifica con `ruff` tras editar.
- **Git Bash convierte rutas** que empiezan con `/` en argumentos: usa `MSYS_NO_PATHCONV=1`.
- Un hook ejecuta `ruff format` al guardar y reescribe archivos (verás «changed on disk»); es esperado. RUF001/RUF003 rechazan `×`, `–` literales: usa escapes `×`, `–`.
- `from_engine.py` ya está formateado a ~970 líneas; `report_input_from_model` lleva `# noqa: PLR0915` a propósito (constructor de documento).
- Puerto 8000: el servidor no recarga solo; reinícialo tras tocar Python. Los tokens demo viejos del navegador ya se renuevan solos.
- Los PDFs/PNG de inspección y scripts auxiliares viven en el *scratchpad* de la sesión (temporal, fuera del repo): no dependas de ellos. `tests/fixtures/engine_report_model.json` (74 KB) es salida real recortada del motor para los tests del informe.
- `mypy --strict` sobre `milpa_core` sigue en 113 errores (deuda previa, no tocada); `references/` no se tocó.

## 6. Archivos creados o modificados en esta tanda
Nuevos: `apps/api/src/api/reports/{pdf,context}.py`, `apps/api/src/api/geo/{__init__,boundary}.py`, `apps/api/tests/{test_reports_pdf_reportlab,test_report_from_engine}.py`, `apps/api/tests/fixtures/engine_report_model.json`, `tests/integration/test_municipal_boundary.py`, `apps/web/src/api/pdf-download.ts`, `apps/web/src/components/report/{ReportSection.tsx,ReportSection.test.tsx}`, `apps/web/src/components/zone/ZoneMap.test.tsx`, `apps/web/src/lib/{boundary.ts,boundary.test.ts}`, este archivo.
Modificados: `apps/api/pyproject.toml`, `uv.lock`, `pyproject.toml` (overrides mypy), `apps/api/src/api/{cli.py,config/settings.py}`, `reports/{contract,service,from_engine,renderer(solo lectura)}.py`, `jobs/handlers/reports.py`, `repositories/farms.py`, `services/{parcels,zones}.py`, `security/privacy.py`, `testkit/reports.py`, `apps/api/tests/{test_reports,test_config_security}.py`, `tests/integration/test_reports_pdf.py`, `tests/contract/test_r4_artifacts.py`, `apps/web/src/{api/client.ts,api/public-access.ts,api/adapters.ts,screens/ReportScreen.tsx,components/zone/{ZoneMap,ZoneComponents}.tsx,styles.css,i18n/{en,es}.json}`.

## 7. Tanda 2026-11-16 (segundo agente) — qué se cerró y qué queda
**Cerrado y verificado (ejecutado):**
- Lint/format/mypy limpios al momento de cerrar el bloque (ruff 0 errores, mypy 107 archivos). `cli.py::build_parser` se partió (`_add_verification_commands`) por PLR0915.
- `cli report-sample` y `bench/runner.py` usan `render_pdf` (ReportLab): `python -m api.cli report-sample` genera PDF sin Docker/Pango.
- `Settings.municipal_boundary_file`: una variable vacía (`${X:-}` de compose) ya es «sin regla» (antes era `Path('.')` → 503 al crear parcelas). Test en `test_config_security.py`.
- `scripts/start_local.ps1` ya no exige Docker (usa `DATABASE_URL` si existe); `MUNICIPAL_BOUNDARY_FILE` en `.env.example`, `docker-compose.yml` y el script.
- ADR-021 (ReportLab) y ADR-022 (límite municipal) + índice (019–022); `docs/MAP_AND_LOCATION.md`; docs de PDF actualizadas (NEXT_STEPS, DEPLOYMENT, REPORTS, TESTING, FINAL_PROJECT_AUDIT, Makefile, marcador `pdf`).
- `tests/contract/test_reference_catalogs.py` (12 pruebas): impide promover a producción valores sin cita en `catalogs/r2/reference/*` (Kc, grados-día, umbrales, ventanas, economía deben seguir `pending*`).
- Web: la demo ya no reutiliza una corrida guardada que el motor no puede recalcular (sondea `/summary`; antes cada gráfico daba 422 tras cambiar la región); la tabla por decenas dice «Fuera de una etapa crítica» / «No aplica umbral» en vez de «Not available»; el mapa ya no deja el veredicto anterior junto al error de coordenadas.
- Navegador (panel): `/demo` crea una corrida nueva y abre `/mvp`; `/calendar` sin errores de consola; `/my-zone`: 12 teselas, límite + zona + celda, leyenda, «dentro de Jocotán», «fuera», «inválido». Sin desbordamiento horizontal a 375 px (la tabla del heatmap y la navegación hacen scroll propio).
- API real extremo a extremo: corrida 2001–2025 → job de informe → `GET /v1/reports/{id}/pdf` 200, **SHA-256 coincide con el registrado**.
- Suites: Python `-m "not slow"` **482 passed, 8 skipped, 1 xfailed, 0 failed** (15 min; antes de añadir las 12 pruebas de catálogos); vitest **51 passed**, ESLint y `tsc -b` limpios, copy-linter 8/8, `vite build` OK.

**Detectado — no resuelto (requiere decisión):**
1. **Hay otro agente editando el repositorio a la vez** (`regions/r2/pilot_corredor_seco.yaml` 05:02 con `plant_window` primera hasta 06-30, `regions/reglas_agronomicas_jocotan.json`, `adapters/agri_context.py`, `services/planting.py`, `routers/zones.py`). Al cerrar, `ruff` marca `routers/zones.py` (I001) y mypy 3 errores en `services/planting.py` (líneas 70, 107, 181): son de ese trabajo en curso, no los toqué.
2. **`make reproduce` vuelve a fallar** (esperado 422 resultados por ciclo, obtenido 530; `results_hash` distinto) porque la región cambió después de que yo refrescara `data/demo/EXPECTED_ENGINE.json` (lo regeneré a las ~04:50 con `python -m api.cli freeze-engine --data-dir data`; el original quedó en el scratchpad). **Cuando la región/catálogos dejen de cambiar, vuelva a ejecutar `freeze-engine` y `reproduce` (debe dar «completado y verificado»).** Cada cambio de región invalida también las corridas ya guardadas (guardia de reproducibilidad: 422 «cambiaron los datos o la configuración»); es el comportamiento diseñado.
3. **i18n:** `apps/web/src/i18n/index.ts` fija `lng = "en"` («el producto es solo inglés»); `HomeScreen`, `MvpScreen`, `DemoScreen`, `PlantsScreen`… tienen inglés fijo. El traspaso pedía paridad es/en: contradice esa decisión de producto, así que **no la hice**. Hace falta que el usuario elija (solo inglés, o es/en con selector).
4. Sin ejecutar: Playwright, pruebas `slow`, imagen Docker/compose smoke, GitHub Actions, ingesta real con red, registro de la celda IMERG en `geo.climate_cell`, nombre legible de zona, atribución del polígono municipal (el archivo no la declara; confirmar con quien lo aportó).

## 8. Tanda 2026-11-16 (pulido de la demo web) — qué se cambió y qué NO se verificó
**Cambios (frontend verificado: tsc, ESLint, vitest 54/54 en serie, copy-linter 8/8, `vite build`; revisado en el navegador del panel):**
- Mapa: las teselas de OpenStreetMap devolvían 403 «Access blocked» porque la API envía `Referrer-Policy: no-referrer`. Mapa base ahora CARTO Voyager (+ `referrerPolicy="origin"`), configurable con `VITE_MAP_TILE_URL`/`VITE_MAP_ATTRIBUTION`.
- `Indicator`: las cifras sin procedencia estructurada («bare») ya no muestran «No evidence level / unknown / Prov.»; valor + unidad y el motivo en el panel «i». Unidad «1» y «year» ya no se imprimen («0.26 1», «2014 year»). Los badges compactos con evidencia real muestran solo «Ev. C» (el detalle en tooltip/lectores de pantalla).
- Cobertura de datos: matriz compacta con tinte, nota única de procedencia, ◐ para año parcial (2025: 25,21 % sin dato), limitaciones con encabezado y traducidas.
- Suelo: SoilGrids se **volvió a ejecutar con el servicio real** (`tools/etl_soilgrids.py`, 3 puntos válidos: arcilla 33,3 %, arena 35,4 %, limo 31,2 %, COS 35,3 g/kg, pH 6,6, densidad 1,3) y la tabla se muestra con etiquetas; en la sesión demo se ocultan identificador/carga/declaración de parcela (no se pueden crear).
- DEM: `milpa-etl fetch dem --tif data/dem/copernicus_glo30_jocotan.tif` aplicado a la BD local → elevación media 816,1 m y pendiente 39,0 % (antes «No disponible»). Etiquetas corregidas (decían «punto de referencia»).
- Lanzador de escenarios: 4 selectores (ΔT, lluvia, retraso, humedad) en lugar del texto libre; los ids generados coinciden con los 44 de `standard_grid` (prueba `ScenarioLauncher.test.tsx` + `grid-ids.fixture.json`). Selector de escenarios con nombres legibles.
- Errores reales corregidos: columna «Ciclo» de la tabla de riesgo mostraba `cycle_idx + 1` (R2 ya es 1-based); `catalog:maiz_corto` se mostraba crudo; etiqueta «MVP1» → «DEMO»; id de corrida acortado; textos «§16» fuera; informe: opciones avanzadas plegadas.
- `SourceStatus`: SoilGrids y DEM pasan a «Integrated» (lo eran ya en la práctica).
- Despliegue sin pasar por la imagen: `infra/scripts/bootstrap-demo.sh` (idempotente) probado **en una base nueva** con los pasos reales: migraciones → `register-engine` → `create-demo-user` → `register manifest/zone/provenance` → `fetch dem`; luego corrida 2001–2025 → informe → PDF (SHA-256 coincide). `entrypoint.sh` lo invoca con `DEMO_PUBLIC_ACCESS`/`BOOTSTRAP_DEMO`. Sección 0 de `docs/DEPLOYMENT.md`.

**NO verificado (el usuario pidió dejar Docker de lado):** `infra/Dockerfile.app` (nueva etapa `web` con Node, `--extra dem`, copia de datos semilla a `/opt/milpa/seed`), `.dockerignore` y `docker-compose.yml` modificados **no se han construido**. Dos intentos de `docker build` tumbaron Docker Desktop por falta de RAM (se reinició con `docker start milpa-test-db`; los datos estaban intactos). No reintentar sin liberar memoria.
**Avisos para decidir:** (1) `regions/r2/pilot_corredor_seco.yaml` usa `elevation_m: 444.74` (píxel del punto de referencia) para el ET0, mientras la media zonal del DEM y la rejilla POWER son 816 m / 762 m: decisión científica del otro agente, no se tocó. (2) `make reproduce` sigue necesitando `freeze-engine` tras estabilizar la región. (3) Base `milpa_fresh` en el contenedor `milpa-test-db` es un resto de prueba (se puede borrar). (4) `data/results/` y `data/reports/` estaban versionados/generados: añadidos a `.gitignore` (no se desversionó nada).

## 9. Tanda 2026-11-16 (validación agronómica, inicio de lluvias y estación Camotán)
Documento completo: `docs/VALIDACION_AGRONOMICA_JOCOTAN.md` (tabla maestra Kc/etapas, fuentes con URL, supuestos, pendientes) y `docs/decisions/ADR-023-validacion-agronomica-jocotan.md`.
- **Código nuevo:** `apps/api/src/api/agronomy/{rules,validation,onset,station,climate,i18n}.py`, `services/agronomy.py`, `schemas/agronomy.py`; `services/planting.py` reescrito sobre ese paquete (sin duplicar reglas). Endpoints: `GET /v1/zones/{id}/planting-options`, `/rainy-season-onset`, `/station-validation` y parámetros nuevos en `planting-validation` (cultivo, ciclo, días secos, lluvia 15 d, `idioma`). 40 operaciones en total (contratos de prueba actualizados).
- **Datos:** `regions/reglas_agronomicas_jocotan.json` v2.0.0 (generado con `tools/agronomy/build_rules_json.py`; se edita el JSON, no el código), `data/estaciones/camotan_ejemplo.csv` (FICTICIO; nunca cambia el estado).
- **Frontend:** `components/zone/{PlantingValidation,RainyOnsetSandbox,StationValidationNotice,AgronomyKinds}.tsx` en «Mi zona»; aviso de evidencia C también en el MVP. Banner «SANDBOX SIMULATION — NOT AN OPERATIONAL ALERT» siempre visible; botón «Upload Station Data (CSV)» deshabilitado a propósito (la demo pública no sube archivos).
- **Verificado:** pruebas unitarias (41), integración con PostGIS (8), vitest (8 nuevos), contratos (112), mypy/ruff limpios; flujo manual en el navegador (frijol + fecha fuera de ventana + 8 días secos → banners de ventana y sequía, tabla Kc/etapas, fuentes). Inicio de lluvias calculado con datos reales 2001-2025: se detecta en los 25 años (p. ej. 2015: 10-jul; 2025: 31-may).
- **Hallazgos de investigación:** B-9 y B-15 sin ciclo en fuentes ICTA (proxy FAO-56 125 d rotulado); B-7 «4 meses» (120 d) frente a 95/110 d de registros previos; el criterio de pentadas es del **Informe 6/2025 de MAGA** (no un método propio de INSIVUMEH) y su redacción sobre las pentadas previa/siguientes es ambigua (interpretación documentada).
- **Pendiente:** serie diaria real de la estación Camotán (colocar en `data/estaciones/camotan_insivumeh.csv`); validación oficial MAGA/ICTA de ventanas y umbrales; Kc/etapas locales; re-verificar Memoria ICTA 2002 (floración B-7=53, B-5=48; cita secundaria) y el Kc ini del maíz en la imagen de FAO-56 Tabla 12.
