# Auditoría de R1 — Datos y evidencia (FASE 2-3)

> **Actualización posterior (ADR-018):** R1 y R4 se integraron en la raíz del repositorio (`packages/milpa_etl`, `apps/web`, `catalogs/`, `regions/`, `data/`). El contrato Parquet zonal de R1 es ahora el que lee R3 (C-02 resuelto en R3; la diferencia con el README §13.7 queda registrada). Las cifras de este documento corresponden a la auditoría previa a esa integración salvo donde se indique.

Artefacto auditado: `references/Milpa-Resiliente-R1` (git `31fe99f`). Método: lectura de código, **ejecución** de sus pruebas, aplicación de su SQL en PostgreSQL/PostGIS real, y lectura de sus Parquet con el lector de R3. Nada de `references/` fue modificado (las ejecuciones usaron directorios temporales fuera del repositorio).

> R1 **no es una estrategia agronómica**: es el paquete de datos. Las 15 dimensiones del encargo (§3) se responden con lo que R1 realmente contiene; donde no hay contenido se dice «no definido» con la evidencia, sin inventar.

## 1. Veredicto resumido

| Aspecto | Resultado |
|---|---|
| Autopruebas de R1 (`python milpa_r1.py selftest`) | **24/24 OK** (ejecutadas aquí, offline) |
| ET0 FAO-56 contra el Ejemplo 18 del manual (Uccle) | 3,88 mm/día frente a 3,9 de referencia (tolerancia 0,15) |
| Fórmulas de ET0 y Pef frente al README §11.3-11.4 | Coinciden en lo comprobado (ver §4); falta la bandera de ET0 negativo |
| Lectura de sus Parquet con el lector de R3 | **Rechazada** (falta `cell_id`): incompatibilidad con README §13.7 (C-02) |
| Lectura de sus CSV de suelo con el validador de R3 | 7 filas válidas aceptadas; las 9 filas inválidas rechazadas con el error esperado (tras corregir R3, C-15) |
| Su DDL frente a las migraciones de R3 | Todo lo de R1 está en R3 salvo 4 puntos (2 `NOT NULL` en `ip_id`, tipos de `engine.job.kind`, nombre de un índice: C-07). R3 solo **añade** (bloqueo de login, `auth.audit_log`, `created_at`, índices). Además C-01 (orden de aplicación) |
| Sus scripts SQL sobre la base de R3 | `92_soil_fixture_provenance.sql` **elimina `security_invoker`** de una vista y abre una fuga de RLS demostrada (S-01) |
| Parámetros agronómicos | **Todos `pending`** (P9 cumplido; no hay estrategias definibles) |

## 2. Hallazgos de compatibilidad (detalle en `matriz_compatibilidad.md`)

| ID | Hallazgo | Severidad |
|---|---|---|
| S-01 | `92_soil_fixture_provenance.sql` hace `CREATE OR REPLACE VIEW soil.property_status` sin `WITH (security_invoker = true)`. Aplicado sobre el esquema de R3, un usuario **sin ninguna parcela** vio 16 filas (2 parcelas × 8 propiedades) de datos ajenos; con la opción restaurada, 0. | **Alta (seguridad)** |
| C-01 | Los archivos `sql/` no se pueden aplicar en el orden de sus nombres: `03_ref.sql` referencia `geo.region` (creada en `04_geo.sql`). Hay que aplicar `04_geo` antes de `03_ref`. | Media |
| C-02 | Parquet sin `cell_id` (serie ponderada por zona, no por celda), sin `tmean_c`, `obs_date` como `timestamp` (no `date`), columnas extra (`precip_power_mm`, `precip_imerg_mm`, cuatro `pef_mm_*`, `pef_month_total_usda_scs_fao`). | Alta. **Resuelto en R3** (contrato zonal, ADR-018); falta que R1/R2 confirmen si la clave por celda del README §13.7 se abandona |
| C-07 | `econ.price_record.ip_id` y `soil.estimate.ip_id` son `NOT NULL` en R1; el README §13.4 los define opcionales. | Baja |
| C-08 | La vista de `92_…` añade una rama `desconocido` por procedencia que el README no define. | Baja |
| C-12 | R1 implementa ET0 y Pef; el README los asigna a `milpa_core` (R2). Duplicación de lógica científica (R1 la rotula «respaldo local; confirmar con R2»). | Media |
| C-13 | `ingestar_suelo_db.py` escribe directamente en la BD (rol propietario, sin RLS ni consentimiento) con evidencia fija C y `evidence_rule_id = 'soil_fixture_c'`, **regla que no existe** en `catalogs/evidence_rules.yaml`. Solo para fixtures sintéticos (lo declara). | Media |
| C-16 | `data_hash` de R1 (`input_hash`/`data_hash` en `curated_meta.json`) y el de R3 se calculan con algoritmos distintos; equivalencia no verificada. | Media |

## 3. Las 15 dimensiones del encargo, aplicadas a R1

| Dimensión | Contenido real de R1 | Evidencia |
|---|---|---|
| Objetivo agronómico | Ninguno. Objetivo: curar clima (POWER, IMERG) y registrar procedencia/evidencia. | `README.md` de R1 |
| Tipo de estrategia | No define estrategias. | — |
| Secuencia de cultivos | No definida. Solo identifica `maiz` (Poaceae) y `frijol` (Fabaceae, leguminosa). | `catalogs/crops.yaml` |
| Calendario y ciclos | **No definido**: `agri_year_start: pending`; zona `pending`. | `regions/pilot_corredor_seco.yaml` |
| Fechas de siembra/cosecha | No definidas. | — |
| Variedades y fenología | `varieties: []` para ambos cultivos; plantilla comentada con todo `pending` (Kc, etapas, raíz, `p`). | `crops.yaml` |
| Requerimientos hídricos | No hay Kc ni demanda. Sí hay ET0 diaria y Pef por decena (clima, no cultivo). | `milpa_r1.py` |
| Parámetros de suelo | Catálogo `ref.soil_property`: `ph` [3,10], `organic_matter`, `sand`, `silt`, `clay` [0,100], `cec` [0,200], `effective_depth` [0,1000] cm, `awc` [0,400] mm/m, con métodos aceptados; `max_age_years` = NULL (vigencia **no definida**). | `sql/91_seed_soil.sql` |
| Indicadores de estrés | Ninguno (umbrales `pending`; DP-05). | `crops.yaml` |
| Criterios de evaluación | Reglas de evidencia A/B/C como «propuesta» (DP-09). | `evidence_rules.yaml` |
| Supuestos científicos | G = 0; Hargreaves–Samani con `krs = 0,16` **[Verificar]**; tolerancia tdew 2,0 °C **[Pendiente]**; Pef con fórmulas USDA-SCS/FAO **[Verificar]** (DP-06). | `milpa_r1.py` líneas 77-80 |
| Fuentes de datos | NASA POWER diario (T2M_MAX, T2M_MIN, T2MDEW, RH2M, WS2M, ALLSKY_SFC_SW_DWN, PRECTOTCORR); IMERG Final V07 (`GPM_3IMERGDF`, 0,1°, 12 celdas ponderadas por área); Copernicus DEM 30 m. Licencias por completar (DE-12/DP-14: IMERG `redistributable=false`). | `milpa_r1.py`, `sql/93_seed_imerg.sql`, README R1 |
| Limitaciones | Declaradas: lluvia evidencia C; oct-dic 2025 solo POWER; 9 días atípicos de POWER (≥ 100 mm con IMERG < 10 mm); IMERG vs POWER **no es validación**; DEM y elevación de prueba; convención de día UTC vs UTC−6 por verificar; polígono aproximado. | README R1, `curated_meta.json` |
| Reglas de validación | QC físico (§RC-D2), relleno ≤ 3 días, lluvia nunca interpolada, cobertura previa al relleno, `validate_series`, `scan_privacy`, `validate_catalog` (falla en `production` si hay `pending`). | `milpa_r1.py` |
| Resultados esperados | `daily.parquet` (9 131 filas), `dekad.parquet` (900), `coverage.parquet` (200), `curated_meta.json`, `precip_validation.json`; procedencia en `prov.indicator_provenance`. | `data/curated/chiquimula_prueba/` |

## 4. Reglas científicas: verificación de la implementación local de R1

| Regla (README) | R1 | Verificación |
|---|---|---|
| ET0 PM, `G=0`, `P` con DEM, `es`, `Δ`, `γ`, `Rn=0,77Rs−Rnl`, `Rso`, `Rs/Rso ≤ 1` (§11.3) | `et0_fao56` | Lectura línea a línea + Ejemplo 18 FAO-56 (3,88 vs 3,9) |
| `max(0, ET0)` **con bandera** si el valor sin acotar fue negativo | `np.maximum(et0, 0.0)` sin bandera | **Brecha menor (SV-04)** |
| `ea` dos rutas por día (`R1_dewpoint`, `R2_rh`) | `ea_method` | `selftest` |
| Pef `usda_scs_fao`, `fao_dependable`, `fixed_fraction`, `upper_bound`; desagregación proporcional; mes con hueco ⇒ NaN (§11.4) | `peff_month`, `build_dekad` | `selftest`: `0≤Pef≤P`, monotonía, suma de decenas = Pef del mes |
| Lluvia nunca interpolada; relleno ≤ 3 días; HS si falta radiación | `clean_climate` | `selftest` |
| `φ` de `fixed_fraction` **[Pendiente]** | `phi=None` ⇒ `NaN` | No se inventa |
| Determinismo (mismo `data_hash` en dos corridas) | `build_demo` | `selftest` |

## 5. Pendientes de validación científica (no son defectos; requieren decisión de R1/R2/asesor)

- **SV-01 — Origen de la lluvia.** 7 397 de 9 131 días (81 %) toman la lluvia de POWER `PRECTOTCORR`; 1 734 (2021-01-01 a 2025-09-30) de IMERG. El README (§21) asigna IMERG nivel B y trata POWER como contraste/respaldo; R1 deja la regla de uso de POWER como primaria «pendiente de R2» (`evidence_rules.yaml`, `precip_power_provisional`). Medido: total anual medio 1 439 mm (2001-2020, POWER) y 1 460 mm (2021-2024, IMERG). En los 1 734 días de la ventana IMERG, `precip_validation.json` (el archivo que el README de R1 declara para esta comparación) reporta correlación diaria 0,124, correlación de sumas por decena 0,194, sesgo −0,968 mm/día y cociente de totales IMERG/POWER 0,813 (por año: 2021 0,524 · 2022 0,650 · 2023 0,763 · 2024 1,003). `validation_report.json`, de una corrida anterior (1 369 días), da 0,144 y 0,774: **los dos archivos de R1 no coinciden** (SV-06). R1 advierte que esto **no es validación**. No se aplicó corrección de sesgo (bit 8 nunca usado; `fallback_cap_mm = null`). **Decisión científica pendiente** (R2/asesor): no la toma R3.
- **SV-02 — Sin parámetros agronómicos.** Sin Kc, fenología, ventanas críticas, umbrales, variedades ni calendario, el motor no puede producir indicadores de exposición críticos (`provisional_sin_cita`) ni definir estrategias. Es el comportamiento correcto según P9; bloquea el piloto (DP-01…05).
- **SV-03 — Ambigüedad de `fallback_share_pct`.** `curated_meta.json` trae `fallback_share_pct = 0.0` (dentro de la ventana IMERG) y `fallback_share_pct_full_series = 81.01`. La regla `precip_imerg_b` baja a C cuando `fallback_share > fallback_share_max [Pendiente]`; no está definido cuál de las dos cifras aplica.
- **SV-04 — ET0 negativo sin bandera** (ver §4).
**SV-07 — `build-demo` no es idéntico bit a bit entre plataformas (medido).** El mismo `build-demo`, con las mismas versiones de pandas 3.1.1 / numpy 2.5.4 / pyarrow 26.0.1, produce `data_hash` distinto en Windows (`a64b22ff…`) y en Linux (`9f56f58c…`): 146 de 9 131 celdas de `daily` y 11 de 900 de `dekad` difieren en el último bit (error relativo máximo 4,6·10⁻¹⁶; `coverage` idéntico). Es la «tolerancia numérica entre plataformas» que prevé el README §25. `make reproduce` exige igualdad exacta del `data_hash` y, si difiere, acepta los datos solo si esquema y valores no numéricos son idénticos y los numéricos cumplen rtol 1e-9 / atol 1e-12 (**provisional**: el README la fija por ADR **[Verificar]**).
- **SV-05 — Convención de día** (UTC vs UTC−6) sin resolver; R1 la declara como limitación.
- **Zona de prueba:** polígono rectangular «dibujado a mano» (`approximate: true`) y `elevation` de prueba; no apto para conclusiones del piloto.

## 6. Recomendaciones a R1 (sin cambiar sus reglas)

1. Corregir `92_soil_fixture_provenance.sql` con `WITH (security_invoker = true)` (S-01) y no ejecutar scripts DDL sobre la base compartida: **R3 es dueño de la cadena Alembic** (ADR-003, pendiente de aprobación).
2. Renombrar/ordenar los SQL para que se apliquen en orden de nombre (`03_geo` antes de `04_ref`) o entregarlos como revisiones Alembic.
3. Decidir con R2/R3 el esquema de Parquet (con o sin `cell_id`) y actualizar README §13.7 o los archivos (C-02).
4. Declarar la regla de evidencia `soil_fixture_c` en `evidence_rules.yaml` o dejar de usarla; que `ingestar_suelo_db.py` no se use fuera de fixtures (C-13).
5. Marcar ET0 sin acotar negativo con bandera (SV-04).
