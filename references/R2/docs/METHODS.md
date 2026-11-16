# METHODS — milpa_core 0.1.0 (R2, SE-12)

Este documento describe exactamente lo que calcula el motor. Las secciones referencian el
documento de arquitectura MILPA RESILIENTE 3.3. Lo marcado **[Propuesto R2]** es una decisión
de implementación tomada por R2 donde el documento no fija la regla; debe confirmarse en un ADR.

## 1. Cadena de cálculo
Serie curada (R1) → ET0 FAO-56 PM y Pef por método → calendario por ciclo → exposición (Modo A)
o balance (Modo B) → agregación por ciclo y por cohorte → criterios → ranking → estabilidad →
escenarios y Soil VoI. Determinista; sin aprendizaje automático; aleatoriedad solo con
`numpy.random.Generator` sembrado (estabilidad y bootstrap del margen).

## 2. Clima (11.3, 11.4)
- **ET0**: FAO-56 ec. 6, G = 0, P con la elevación del DEM (`zone.elevation_m`), Rso = (0.75+2e-5 z)·Ra,
  Rnl con Rs/Rso acotado a 1, resultado acotado a ≥ 0. Si falta Rs se usa Hargreaves–Samani (kRs 0.16)
  y la evidencia de ET0 baja a C.
- **ea, dos rutas por día**: R1 = e°(T2MDEW) si existe y Tdew ≤ Tmax + 0.5 °C; R2 = RH2M/100·es.
  ea se acota a es. Se calcula la diferencia de ET0 total entre rutas; si supera
  `ea_sensitivity_tol_pct` se declara `ea_sensible_a_la_ruta`.
- **Pef** en escala nativa: `usda_scs_fao`, `fao_dependable` (mensuales) y `fixed_fraction`,
  `upper_bound`. Los mensuales se desagregan a días por P_d/P_mes (suma por decena = Pef de la
  decena; por mes = Pef mensual). Mes con algún día de P faltante **o incompleto en la serie** → NaN
  (nunca relleno).
- **Decenas**: 1–10, 11–20, 21–fin de mes (36 por año).

## 3. Cultivos y calendario (11.5)
Kc lineal de `kc_start` a `kc_end` dentro de cada etapa (cubre constante e interpolación FAO-56).
Fenología en días o en GDD (base y totales citados; si el total no se alcanza con datos, el ciclo
no es evaluable). `harvest_date` = último día del ciclo. Ajuste climático de Kc desactivado (POWER
no entrega RHmin).

## 4. Estrategias y cohortes (11.6)
- Fechas: `candidate_dates` → fecha ancla; `fixed_season_window` → inicio de la ventana de la
  temporada en su año calendario; `relative_to_previous_harvest` → **cosecha_{k−1} + 1 + reposo_{k−1}
  + rel_lag_days [Propuesto R2]**.
- Año calendario del ciclo = cohorte + `agri_year_offset` + `calendar_year_shift` de la temporada.
- Una cohorte entra solo si todas sus fechas caen en la ventana de datos.
- Validadores: `cycle_idx` 1..n; un solo ciclo barre fechas y es el ancla; Σ area_fraction = 1;
  el primer ciclo no puede ser relativo; offsets no decrecientes.

## 5. Modo A — exposición (11.7)
Segmentos = decena ∩ etapa crítica, con prorrateo de decenas parciales; e = max(0, ETc − Pef).
Umbral `dekad_exposure_mm` escalado por n_días/días_de_la_decena; también `stage_cum_exposure_mm`
y `pef_over_etc_ratio` por etapa. Cada componente de una asociación se evalúa solo; el ciclo es
crítico si algún componente lo es. **Severidad del ciclo = máximo de las severidades de los
componentes [Propuesto R2]**; se reportan las de cada componente. Sin umbral para una etapa
crítica → `insufficient_data` con `provisional_sin_cita`. Umbral sin cita (sandbox) → se calcula
con `provisional = true` y evidencia C. Pef NaN en el ciclo → `not_evaluable`.
Segmentos con menos de `min_segment_days` días (región; 5 en el piloto) **[Propuesto R2]** suman a la
severidad pero no se comparan con el umbral: evita que un día seco en el borde cuente como decena seca.
Sensibilidad: cada ciclo se evalúa con los umbrales bajo/central/alto y con cada método de Pef habilitado.

## 6. Modo B — balance (11.8)
Cubeta diaria FAO-56 con P diaria (no Pef), RO = 0, sin ascenso capilar, Kc único; Zr crece lineal
de z_min a z_max hasta el fin de la 2.ª etapa **[Propuesto R2]** y se limita por la profundidad
efectiva. Severidad = Σ(1 − Ks) en días críticos. Solo corre si `decide_mode` lo autoriza.
Pendiente: corrida con Dr0 = 0 para `sensible_a_condicion_inicial`, `soil_carryover` y spin-up.

## 7. Agregación (11.9)
- Por ciclo: frecuencia sobre decididos, mediana/P90 (interpolación lineal), CVaR90 = media de
  severidades ≥ P90 (descriptivo), peor año, cola = P90 / max(mediana, ε). `n_valid < min_valid_years`
  → `datos_insuficientes`.
- Por cohorte: lógica trivalente (crítica si algún ciclo lo es; no crítica solo si todos son no críticos).
- Invariantes al horizonte para el ranking: proporción agrupada de ciclos críticos; P90 de la
  severidad sumada por año agrícola (solo cohortes completas); cociente de cola.
- Consistencia relativa (≥ 3 estrategias comparables) **[Propuesto R2]**: tercil superior de cola →
  `fallos_en_años_desfavorables`; si no, tercil superior de frecuencia → `variable`; si no, `consistente`.
- Ventana consistente: ≥ 3 fechas contiguas con frecuencia ≤ Q1 y P90 < mediana (descriptiva).

## 8. Criterios (11.10)
- **Agua** = 1 − proporción agrupada de ciclos críticos **[Propuesto R2]**; subindicadores visibles.
- **Suelo** = media de subindicadores disponibles comunes a todas las estrategias (aporte de N
  condicionado, meses de cobertura/12, diversidad de familias/3, retorno de residuos, penalización
  por repetir familia, compatibilidad de pH). Cobertura < `min_subindicator_coverage` → no evaluable.
- **Alimentación** y **ingresos**: solo con rendimientos de referencia, composición y precios con
  cita; si faltan, `not_evaluable` (nunca cero).
- Elegibilidad: cultivo habilitado, restricciones declaradas, pH fuera del rango absoluto solo con pH
  conocido y matriz con cita.

## 9. Ranking y estabilidad (11.11, 11.12)
Soporte común, pesos efectivos, cobertura mínima de pesos, min–max sobre E (o escala de referencia),
criterio constante → 0.5 y `non_discriminating`, desempate por puntuación hídrica y código,
explicación por pares, `decision_log`. Margen: bootstrap pareado de años agrícolas sobre el criterio
hídrico; `margin_within_uncertainty` si el percentil 5 de la diferencia ≤ 0 **[Propuesto R2]**.
Fecha ancla de una estrategia que barre fechas en el ranking: inicio de su ventana
(`window_start`, sin sesgo de selección) o explícita por estrategia **[Propuesto R2]**.
Estabilidad: Dirichlet (concentración 50) o bola proyectada al símplex; solo criterios de C.

## 10. Escenarios (19)
Orden: retraso de inicio → escalado de P → ΔT (humedad `constant_rh` o `constant_ea`) → ET0 y Pef
recalculados. El retraso se aplica por año agrícola (desde `agri_year_start`); la lluvia que sale del
año se reporta como `mass_dropped_mm` (**sin buffer_days todavía**). Inicio de lluvias: primer día
húmedo con Σ ≥ X mm en N días y sin racha seca > Y en los Z siguientes. Año sin inicio →
ciclos `not_evaluable`. Evidencia de salidas con tope C. Grilla: 1 + 8 + 18 + 18 = 45.

## 11. Soil VoI (20)
pH medido → `already_measured`; sin ranking base → `not_applicable`; sin rango (p05–p95 o rango
citado) o sin matriz con cita para los top-k → `insufficient_info`; si no, n_hyp valores
equiespaciados, re-ranking con mismos pesos y soporte común; `ranking_sensitive` → laboratorio
recomendado. Cada valor se rotula «valor hipotético, no medido».

## 12. Evidencia (21)
`IndicatorBuilder` calcula la evidencia como mínimo de sus entradas (nunca máximo); procedencia
desconocida → evidencia nula. Lluvia IMERG sin validación local = C (decisión de R1).
