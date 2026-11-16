# Reglas consolidadas (FASE 2)

Solo se incluyen reglas **leídas en las fuentes**, citadas por archivo y sección. No se agregó ni se infirió ninguna regla agronómica. «Dueño» = paquete que la implementa según el README §«Equipos». «Estado en el repositorio» describe lo que existe **hoy** (ver `matriz_trazabilidad.md` para código y pruebas).

Convenciones: `[Pendiente]` = el README la deja sin valor; `[Verificar]` = el README pide verificación; R2 = `milpa_core` (no existe).

## A. Principios transversales (`README.md` §5, P1–P10)

| ID | Regla | Dueño | Estado en el repositorio |
|---|---|---|---|
| RC-P1 | El núcleo (`milpa_core`) no hace E/S ni importa FastAPI/SQLAlchemy/requests | R2 | R3 no importa ni reimplementa ciencia; frontera verificada por `tests/contract/test_boundaries.py` |
| RC-P2 | Ningún número sale sin procedencia y nivel de evidencia (`Indicator`) | R2 | R3 transporta `ProvenanceInfo`; R3 no asigna evidencia (ADR-009). R4 propone envolver **todas** las cifras en `Indicator` (SPEC-01, C-11) |
| RC-P3 | El motor decide el modo (`exposure`/`root_zone`) por gating | R2 | No existe; R3 solo guarda `mode`/`mode_reasons` |
| RC-P4 | Configuración sobre código (region pack, catálogos versionados) | R1/R2 | `regions/pilot_corredor_seco.yaml` y `crops.yaml` de R1 existen **vacíos (`pending`)** |
| RC-P5 | Reproducibilidad: `code_version`, `config_hash`, `catalog_hash`, `data_hash`, semilla | R2/R3 | R3: hashes canónicos, `RunIdentifiers`, `make reproduce` (exit 2/3 sin datos) |
| RC-P6 | Degradación explícita: falta un dato ⇒ baja evidencia, cambia modo o `not_evaluable` | R2 | R3: faltantes se devuelven `null`, nunca 0 (CSV, Parquet); decisión científica de R2 |
| RC-P8 | Un contrato, una definición (enums) con paridad Python↔SQL↔OpenAPI | R2 | Espejo provisional en R3 + `test_enum_parity.py`; R4 coincide con el espejo (`test_r4_artifacts.py`) |
| RC-P9 | **Ningún valor agronómico inventado**: sin cita ⇒ `pending` + sandbox rotulado | R1/R2 | R1 lo cumple (`crops.yaml`, `region`); R3 y R4 no introducen valores |
| RC-P10 | Infraestructura proporcional (sin Redis/Celery/Dask/MinIO…) | todos | R3 cumple (2 servicios) |

## B. Datos y calidad (`README.md` §9)

| ID | Regla | Fuente | Dueño | Estado |
|---|---|---|---|---|
| RC-D1 | Curated por zona: `daily.parquet`, `dekad.parquet`, `coverage.parquet`; `curated_meta` con `data_hash` | §9 (línea 312), §13.7 | R1 | Existen para `chiquimula_prueba`; **esquema difiere de §13.7** (C-02) |
| RC-D2 | QC físico: `tmax/tmin` ∈ [−60, 60] y `tmax ≥ tmin`; `rh` ∈ [0,100]; viento ≥ 0; `srad` ∈ [0, Ra]; `precip` ≥ 0; fuera de rango ⇒ nulo + bit 2 | §9 (343-352) | R1 | Implementado en `milpa_r1.clean_climate` |
| RC-D3 | `tdew` > `tmean` + tolerancia ⇒ bandera y ruta `RH2M` ese día | §9 (349) | R1 | Implementado (`TDEW_TOL_C = 2.0` **[Pendiente]**) |
| RC-D4 | **La precipitación nunca se interpola**; un hueco de lluvia reduce `n_valid_days` | §9 (356) | R1 | Implementado y probado (`selftest`) |
| RC-D5 | Relleno lineal ≤ 3 días (bit 4) para T, tdew/rh, viento, radiación; radiación faltante ⇒ Hargreaves–Samani (bit 16, evidencia C) | §9 (357) | R1 | Implementado (`HS_KRS = 0.16` **[Verificar]**) |
| RC-D6 | Bits `qc_flags`: 1 faltante · 2 fuera de rango · 4 relleno · 8 sesgo corregido · 16 radiación modelada · 32 respaldo de otra fuente | §9 (bits 1, 2, 4, 16) y README de R1 | R1 | Bits 1,2,4,16,32 usados; **bit 8 nunca se asigna** (no hay corrección de sesgo) |
| RC-D7 | Ciclo evaluable si % faltante de lluvia y de **cada** variable de ET0 ≤ máximos del region pack (por variable, no `any`) | §11.2 | R2 | No existe; máximos **[Pendiente]** |
| RC-D8 | Un año/ciclo no evaluable se registra (`not_evaluable`), nunca se rellena ni se descarta en silencio | §9 (359) | R2 | No existe |
| RC-D9 | IMERG diario se agrega por día UTC; Guatemala es UTC−6; se documenta como limitación | §9 (341) | R1 | Declarada en `curated_meta.limitations` |
| RC-D10 | Cada descarga crea fila en `prov.ingestion_run` y línea en `manifest/ingestions.jsonl` (SHA-256) | §9 (314) | R1 | `cargar_manifiesto.py`, `curated_meta.raw_sha256` |
| RC-D11 | `data_hash` = SHA-256 de la lista ordenada de `raw_sha256` + hash lógico del Parquet | §25 (línea 2104) | R1/R3 | R1 produce `data_hash`; R3 tiene `data_hash` canónico propio (equivalencia **no verificada**: C-16) |

## C. CSV de suelo (`README.md` §9, líneas 361-368 y §13.4)

| ID | Regla | Estado |
|---|---|---|
| RC-S1 | Formato ancho, UTF-8, punto decimal; columnas `parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,effective_root_depth_cm,awc_mm_per_m,awc_method` | R3 `SOIL_CSV_V1` (corregido en esta auditoría); R1 `suelo.csv` lo cumple |
| RC-S2 | Una fila por muestra; celda vacía = «no medido», **nunca cero**; cada propiedad con valor exige su método | R3 y R1 |
| RC-S3 | `ph` ∈ [3, 10] con `ph_method` obligatorio (agua y CaCl₂ no equivalentes) | R3 y R1 |
| RC-S4 | `sand + silt + clay = 100 ± 2`; fecha no futura | R3 y R1 |
| RC-S5 | `effective_root_depth_cm` y `awc_mm_per_m` opcionales; solo activan Modo B si cumplen §11.1 | R2 (gating) |
| RC-S6 | Vacíos ⇒ la propiedad queda `desconocido`, no `medido` | R3 (sin fila) + vista `soil.property_status` |
| RC-S7 | El pH `medido` no calcula Soil VoI (`already_measured`) | R2 |

## D. Ciencia del motor (`README.md` §11) — dueño R2, **no implementada**; R1 trae una versión local

| ID | Regla | Fuente | R1 (`milpa_r1.py`) |
|---|---|---|---|
| RC-C1 | Gating: Modo B solo con AWC medido (o PTF documentada), profundidad efectiva medida/declarada, Dr0 declarado y catálogo radicular citado; si no, Modo A. Sin valores por defecto del código | §11.1 | No aplica (no es del ETL) |
| RC-C2 | ET0 FAO-56 Penman–Monteith, `G = 0`; `P = 101.3·((293−0.0065z)/293)^5.26` con elevación del DEM; `es`, `Δ`, `γ`; `Rn = 0.77·Rs − Rnl`; `Rso = (0.75+2·10⁻⁵z)·Ra`; `Rs/Rso ≤ 1`; resultado `max(0, ET0)` **con bandera si el valor sin acotar fue negativo** | §11.3 | Fórmulas coinciden (verificado por lectura y por el Ejemplo 18 de FAO-56: 3,88 vs 3,9). **No marca bandera** cuando el ET0 sin acotar fue negativo |
| RC-C3 | `ea` por dos rutas registradas por día: R1 `e°(Tdew)` (preferente) y R2 `(RH2M/100)·es`; limitación `ea_sensible_a_la_ruta` si la diferencia supera `ea_sensitivity_tol` **[Pendiente]** | §11.3 | Implementado (`ea_method`); `validation_report.json` reporta diferencia media 0,149 mm/día |
| RC-C4 | Pef por decena: `usda_scs_fao` (`P≤250: P(125−0,2P)/125; si no 125+0,1P`), `fao_dependable` (`P≤70: máx(0,0,6P−10); si no 0,8P−24`), `fixed_fraction` (`φ`, **[Pendiente]**), `upper_bound` (`Pef=P`); desagregación `Pef_d = Pef_mes·P_d/P_mes`; mes con algún día faltante ⇒ `NaN` | §11.4 | Implementado y coincide con el texto (`peff_month`, `build_dekad`); `φ` ausente ⇒ `NaN` |
| RC-C5 | Propiedades: `0 ≤ Pef ≤ P`, `Pef=0` si `P=0`, monotonía mensual, suma de decenas = Pef del mes | §11.4 | Probadas en `selftest` |
| RC-C6 | Kc y fenología por variedad **con cita**; sin cita ⇒ `pending` y solo sandbox; etapas críticas con cita propia o el ciclo queda `provisional_sin_cita` | §11.5 | Catálogo vacío (`pending`) |
| RC-C7 | Asociación: **no** usar `Σ f_i·Kc_i` para el indicador de exposición (cada componente se evalúa con su Kc/ventana/umbral; el ciclo es crítico si algún componente lo es); la suma solo como línea exploratoria (evidencia C) | §11.5 | No existe (R2) |
| RC-C8 | Leguminosa ≠ mejora de fertilidad por sí misma (depende de nodulación, biomasa, residuos…) | §11.5 | `crops.yaml: fixes_n_conditions: pending` |
| RC-C9 | **Asociación ≠ rotación ≠ cambio de fecha ≠ cambio de variedad**; `changes_from_reference ⊆ {association, rotation, planting_date, variety, cover_crop}`; un cambio de fecha **nunca** se rotula rotación | §11.6 | DDL (`ref.strategy*`, `strategy_axis_t`) en R1/R3; lógica en R2 |
| RC-C10 | Estrategia = secuencia de ciclos (`cycle_idx`, `agri_year_offset`, `season`, `window_mode`, `plant_window`, `fallow_after_days`, `soil_carryover`); `harvest_date` **derivada**, nunca declarada; la unidad de análisis es la **cohorte de inicio** | §11.6 | DDL; lógica en R2 |
| RC-C11 | Año agrícola: `agri_year_start` **[Pendiente]** + `calendar_year_shift` por temporada | §11.6 | `pilot_corredor_seco.yaml: agri_year_start: pending` |
| RC-C12 | Cohorte: `critical` si algún ciclo evaluable lo es; `non_critical` solo si todos son evaluables y ninguno crítico; si no, `insufficient_data`. Cohortes solapadas no son independientes (`⌊N/H⌋`) | §11.6 | R2 |
| RC-C13 | Modo A: exposición `max(0, ETc − Pef)` por decena en etapas críticas; la decena es la unidad; decenas parciales prorrateadas; `severity_mm = Σ e`; sin umbral ⇒ `insufficient_data` (`provisional_sin_cita`) | §11.7 | R2 |
| RC-C14 | **Precipitación menos ETc no es déficit real del suelo** (Modo A se rotula «indicador de exposición climática») | §2 glosario, §11.7 | Etiquetas `Label` espejadas; el texto lo fija R2 |
| RC-C15 | Modo B (balance diario TAW/RAW/Ks/Dr) usa la precipitación diaria que llega al suelo, **no** Pef por decena; `RO=0`, sin ascenso capilar, Kc único; `Dr0` declarado con corrida de sensibilidad | §11.8 | R2 |
| RC-C16 | Agregación robusta: `freq_critical_pct`, mediana, P90, CVaR90, peor año, `tail_ratio`, sensibilidad a umbral y a método de Pef; `n_valid`/`n_expected` siempre visibles; etiqueta relativa solo con ≥ 3 estrategias | §11.9 | R2 |
| RC-C17 | Heatmap: dos vistas (ciclo/estrategia) con cuatro estados (`critical`, `non_critical`, `insufficient_data`, `not_evaluable`), patrón no solo color; un ciclo ancla barre fechas (`MULTIPLE_SWEEP_CYCLES`) | §11.9 | R2/R4 |
| RC-C18 | Ranking: soporte común, pesos efectivos `w'=w/Σw`, `weight_coverage`, `decision_log`, ninguna estrategia gana por tener menos datos; evidencia = mínima de criterios con peso > 0; estabilidad = sensibilidad a pesos, **no** probabilidad | §11.11, §2 | R2 |
| RC-C19 | Criterios no hídricos (suelo, alimentación, ingresos): sin rendimientos/precios/costos con cita ⇒ `not_evaluable`; los desconocidos nunca se vuelven cero; beneficio neto fuera del MVP | §11.10 | R2/R1 |
| RC-C20 | Escenarios: perturbaciones **sintéticas** deterministas; no son pronóstico | §2 | R2 |

## E. Evidencia y procedencia (`README.md` §21; `catalogs/evidence_rules.yaml` de R1)

| ID | Regla | Estado |
|---|---|---|
| RC-E1 | Evidencia A/B/C por regla auditable; **la evidencia de un indicador es el mínimo de la de sus insumos**; un nivel nunca sube | R1 lo implementa en `registrar_procedencia.py` (`min_evidence`) |
| RC-E2 | IMERG es B; baja a C si la fracción de respaldo supera `fallback_share_max` **[Pendiente]** o si **no hay validación en la zona** (IMERG frente a POWER **no** cuenta) | R1 asigna **C** (sin estación) — consistente |
| RC-E3 | Radiación modelada (Hargreaves–Samani) ⇒ ET0 evidencia C | R1 lo implementa (`et0_c_rad_modeled`) |
| RC-E4 | Sin validación local, el máximo es B (`max_level_without_local_verification`) | R1 `limits` |
| RC-E5 | Asociaciones con `Σ f_i·Kc_i`, `fixed_fraction` sin cita, precios sin fuente, umbrales provisionales ⇒ C | §21 (línea 1858) |
| RC-E6 | Toda cifra lleva procedencia: fuente/producto/institución, versión, periodo, resolución, método, fecha de recuperación, supuestos y limitaciones | `prov.indicator_provenance` (DDL §13) |

## F. Backend / plataforma (`Especificacion_Tecnica_MILPA_R3.md`, `README.md` §16, §22)

| ID | Regla | Fuente |
|---|---|---|
| RC-B1 | API `/v1` con OpenAPI; errores `application/problem+json` con `type,title,status,code,detail,request_id,errors,hint`; `GET /healthz` público sin prefijo | R3 §536, README §16 (1529, 1566) |
| RC-B2 | Plantillas de ruta con `{id}`, `{v}`, `{property}`, `{ip_id}` | README §16 (1549-1566) |
| RC-B3 | Listados paginados por cursor `Page[T] = {items, next_cursor}` | R3 línea 489 |
| RC-B4 | Trabajos: `202` + `Location: /v1/jobs/{id}`, `Idempotency-Key`, estados `queued/running/ok/failed/cancelled`, reencolado de `running` huérfanos | README 1572, R3 §715-742 |
| RC-B5 | JWT + Argon2id; RBAC por pertenencia; RLS con `SET LOCAL app.user_id`; consentimiento por propósito; borrado de parcela como trabajo | R3-F02…F06 |
| RC-B6 | Privacidad: sin geometría exacta; ubicación generalizada ≥ 1 km; sin coordenadas/correos/nombres en logs, PDF `public` ni `data/demo/` | R3 §9, README §22 |
| RC-B7 | PDF: Jinja2 + WeasyPrint sin recursos externos (`url_fetcher` local); hash SHA-256 registrado | README §22, R3-F20 |
| RC-B8 | Docker con 2 servicios; reproducible con `make demo`/`make reproduce` | R3 §BE-09/10 |

## G. Producto / presentación (`README.md` §2, §17; `references/R4/docs/PRODUCT_TRACEABILITY.md`)

| ID | Regla | Dueño |
|---|---|---|
| RC-U1 | El producto **no** es pronóstico, simulador de rendimiento ni recomendación automática; no afirma «mejor estrategia para su parcela» | R4/R2 |
| RC-U2 | Estados de datos con texto y patrón (no solo color); `loading/empty/error/insufficient_data/provisional` | R4 |
| RC-U3 | La UI no calcula ciencia; no inventa procedencia; el valor hipotético nunca se presenta como medición | R4 |
