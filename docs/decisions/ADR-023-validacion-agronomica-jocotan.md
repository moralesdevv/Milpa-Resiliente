# ADR-023: Validación agronómica de Jocotán (reglas en JSON, inicio de lluvias sandbox y validación con estación)

- **Fecha:** 2026-11-16 · **Estado:** **propuesto**
- **Contexto:** hacía falta convertir los calendarios, parámetros agronómicos y datos climáticos en una validación trazable y actualizable, sin presentar como oficial lo que es provisional.

## Decisión
1. **`regions/reglas_agronomicas_jocotan.json` es la fuente única** de ventanas de siembra, variedades, Kc, duraciones de etapas, umbrales, criterio de pentadas y configuración de la estación. El código no contiene esos valores.
2. Paquete `api.agronomy` (puro, sin red): `rules`, `validation`, `onset`, `station`, `i18n`. La capa de servicios (`services/planting.py`, `services/agronomy.py`) solo lee la serie curada y llama a esas funciones. No duplica la ciencia de `milpa_core`.
3. **Nuevas operaciones GET** (de 35 a 38): `/v1/zones/{id}/planting-options`, `/rainy-season-onset`, `/station-validation`; y `planting-validation` gana parámetros opcionales (`cultivo`, `ciclo`, `dias_secos_recientes`, `lluvia_15_dias_mm`, `idioma`). Todas de solo lectura y disponibles en la sesión demo.
4. El estado por defecto de la lluvia satelital es **«Nivel C - Pendiente»**; solo un CSV real de la estación, con ≥ 365 días coincidentes, puede dar «Nivel B». La interfaz **no** sube archivos (decisión de seguridad de la demo pública).
5. El inicio de lluvias usa el criterio de pentadas de MAGA (Informe 6/2025) y se rotula siempre como escenario sandbox, no como método oficial de INSIVUMEH.

## Alternativas descartadas
- Poner los parámetros en el código o duplicarlos en el catálogo de R2: dos fuentes que divergen.
- Subir el CSV desde la página pública: permitiría escribir en el servidor sin cuenta.
- Presentar B-9/B-15 con ciclo propio: no hay fuente; se usa un proxy rotulado.

## Consecuencias / riesgos
- Los umbrales hídricos y las ventanas son del equipo (sin cita agronómica): todo resultado es provisional.
- Los Kc son proxies FAO-56; las duraciones de etapas son derivadas.
- El criterio de pentadas tiene una redacción ambigua en la fuente; la interpretación elegida está documentada y es configurable.

**Módulos:** `api/agronomy/*`, `services/{planting,agronomy}.py`, `routers/zones.py`, `schemas/{parcels,agronomy}.py`, `apps/web/src/components/zone/*`, `docs/VALIDACION_AGRONOMICA_JOCOTAN.md`. **Aprobadores:** R3, R4; asesor agronómico MAGA/ICTA para los valores.
