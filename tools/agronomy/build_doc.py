"""Genera docs/VALIDACION_AGRONOMICA_JOCOTAN.md y el ADR-023 a partir del JSON de reglas (tabla y fuentes)."""

import json
from pathlib import Path

d = json.loads(Path("regions/reglas_agronomicas_jocotan.json").read_text(encoding="utf-8"))

rows = [
    "| Cultivo | Variedad | Etapa FAO | Duración (días) | Kc | Fuente | Confianza | Tipo de dato | Supuesto aplicado |",
    "|---|---|---|---:|---|---|---|---|---|",
]
for r in d["parametros_fenologicos"]:
    kc = (
        f"{r['kc_inicio']:.2f}"
        if r["kc_inicio"] == r["kc_fin"]
        else f"{r['kc_inicio']:.2f} → {r['kc_fin']:.2f}"
    )
    rows.append(
        f"| {r['cultivo']} | {r['variedad']} | {r['etapa_fao']} | {r['duracion_dias']} | {kc} | {', '.join(r['fuente'])} | {r['confianza']} | {r['tipo_dato']} | {r['supuesto_aplicado'][:140]}… |"
    )
table = "\n".join(rows)

src = []
for k, v in d["fuentes"].items():
    fecha = f", {v['fecha']}" if v.get("fecha") else ""
    src.append(
        f"- **{k}** — {v['titulo']} ({v['institucion']}{fecha}). {v['url'] or 'sin URL'}. _{v['nota']}_"
    )
sources = "\n".join(src)

DOC = """# Validación agronómica y climática — Jocotán (Chiquimula)

> **Estado: PROVISIONAL.** Todos los parámetros son referencias pendientes de validación oficial MAGA/ICTA y de calibración local.
> Nada de lo que muestra la aplicación es una recomendación oficial ni una alerta operativa.

## 1. Qué se implementó
| Pieza | Dónde |
|---|---|
| Fuente central de parámetros | `regions/reglas_agronomicas_jocotan.json` (v2.0.0). Se generó con `tools/agronomy/build_rules_json.py`; **para cambiar valores se edita el JSON**, no el código |
| Carga con errores controlados | `apps/api/src/api/agronomy/rules.py` (archivo ausente o mal formado → 503 solo en estos endpoints; el resto de la API sigue) |
| Validación de siembra | `agronomy/validation.py::validar_siembra` → `GET /v1/zones/{id}/planting-validation` |
| Inicio de lluvias (sandbox) y retraso | `agronomy/onset.py::detectar_inicio_lluvias` y `evaluar_retraso_adaptacion` → `GET /v1/zones/{id}/rainy-season-onset` |
| Validación con estación Camotán | `agronomy/station.py::validar_con_estacion_local` → `GET /v1/zones/{id}/station-validation` |
| Opciones del formulario | `GET /v1/zones/{id}/planting-options` (salen del JSON) |
| Interfaz | `apps/web/src/components/zone/PlantingValidation.tsx`, `RainyOnsetSandbox.tsx`, `StationValidationNotice.tsx`, `AgronomyKinds.tsx`, en «Mi zona» (el aviso de evidencia también en el MVP) |
| Mensajes es/en | `agronomy/i18n.py` (parámetro `idioma=es\\|en`) |
| CSV de ejemplo (FICTICIO) | `data/estaciones/camotan_ejemplo.csv` |

## 2. Metodología
1. **Fenología.** Se buscaron ciclos y floración por variedad en fuentes primarias (ICTA, FAO). Cuando solo existe el ciclo total, las etapas FAO (inicial, desarrollo, media, final) se **derivan** repartiendo ese total con las proporciones de la Tabla 11 de FAO-56 (método del mayor resto, suma exacta; una prueba comprueba que la suma de etapas = ciclo). Si no se encontró ciclo, se usa la fila FAO-56 de maíz grano de 125 d como **proxy rotulado**, nunca como medición de ICTA.
2. **Kc.** Son proxies FAO-56 Tabla 12 (maíz grano: 0.30 / 1.20 / 0.35; frijol seco: 0.40 / 1.15 / 0.35), con interpolación lineal en desarrollo y final. No existe Kc medido por variedad ICTA en las fuentes consultadas. FAO-56 da Kc fin del maíz 0.60 si se cosecha con humedad alta; se usa 0.35 (secado completo en campo). No se aplicó ajuste climático (HRmin/viento) porque POWER no entrega HRmin.
3. **Validación de siembra.** Cultivo y variedad permitidos, ciclo válido, fecha dentro de la ventana (límites inclusivos), días secos ≥ umbral → alerta de sequía, lluvia de 15 días < mínimo → alerta. Una fecha fuera de ventana es una advertencia de compatibilidad con el calendario, **no una prohibición**. Los umbrales hídricos son los provistos por el equipo (sandbox, sin cita agronómica).
4. **Inicio de lluvias.** Criterio de pentadas del Informe No. 6 de MAGA (8-may-2025, datos INSIVUMEH/ICC, adaptado de Alfaro, Cid y Enfield 1999): pentada ≥ 25 mm y una o ambas de las dos siguientes también; pentadas previa y siguientes > 0.5 mm. Texto leído directamente del PDF. **No es un procedimiento metodológico propio de INSIVUMEH** (no se localizó) y la redacción sobre las pentadas «anteriores y posteriores» es ambigua: aquí se exige > 0.5 mm en la previa y en las dos siguientes (modo estricto `ambas_siguientes` disponible en el JSON). Los días sin dato nunca se tratan como cero: una pentada incompleta no es evaluable. Las pentadas se fijan por fecha de calendario desde el 1 de enero (73 por año; el 29-feb se suma a la pentada 12).
5. **Estación Camotán.** Sin CSV real el estado es «Nivel C - Pendiente». Con un CSV real (`fecha,precipitacion_mm`, mm/día) se calculan RMSE, sesgo (satélite − estación) y r de Pearson **solo con fechas coincidentes**; el Nivel B exige ≥ 365 días coincidentes (configurable) y correlación calculable. El Nivel B significa validación del producto (IMERG) y periodo evaluados, no de todo el sistema. El CSV de ejemplo, o cualquier archivo marcado como ficticio, **nunca** cambia el estado.

## 3. Tabla maestra de parámetros fenológicos y Kc
__TABLE__

Los supuestos completos están en el JSON (`supuesto_aplicado`, `supuestos_generales`). Valores en conflicto para ICTA B-7: ciclo 95 d (guía general ICTA, registro previo) · 110 d a cosecha (Memoria ICTA 2002, registro previo) · **120 d** (ICTA 2015, oriente; usado).

**Variedades sin dato de ciclo (NO ENCONTRADO):** ICTA B-9 e ICTA B-15 (la página del programa de maíz de ICTA no publica ciclo ni floración). Se usa el proxy FAO-56 y la interfaz lo advierte.

## 4. Fuentes consultadas
__SOURCES__

No se pudo re-verificar en esta pasada: la Memoria ICTA 2002 (escaneo de muchas páginas); el Kc inicial del maíz de FAO-56 está en una imagen de la tabla (valor 0.30 de la tabla publicada, verificar contra el original).

## 5. Estado de evidencia
| Elemento | Estado |
|---|---|
| Ventanas de siembra, umbrales hídricos, rango de temperatura | **Provisional** (sin cita agronómica; reglas del equipo) |
| Ciclo/floración de frijol ICTA Ostúa y Santa Gertrudis | Encontrado en ICTA/FAO 2011, Cuadro 1; etapas derivadas |
| Ciclo de maíz ICTA B-5 / B-7 | Encontrado (90 d / «cuatro meses»); etapas derivadas |
| Ciclo de maíz ICTA B-9 / B-15 | NO ENCONTRADO — proxy FAO-56 |
| Kc | Proxy FAO-56 (no medido por variedad) |
| Precipitación satelital vs. estación | **Nivel C — validación local pendiente** |
| Inicio de lluvias | Escenario sandbox, no usar para decisiones operativas |

## 6. Cómo actualizar los parámetros sin tocar el código
1. Edite `regions/reglas_agronomicas_jocotan.json` (ventanas en `ventanas_siembra`, umbrales en `cultivos.<cultivo>.umbrales_hidricos`, criterio de pentadas en `inicio_lluvias`, estación en `estacion_local`). `tools/agronomy/build_rules_json.py` solo sirvió para generar la primera versión con las sumas de etapas verificadas; no hace falta volver a ejecutarlo.
2. La ruta de las reglas se configura con `PLANTING_RULES_PATH` y la del CSV de estación con `STATION_CSV_PATH`. El archivo se lee en cada petición: no hace falta reiniciar.
3. Para activar la validación local, coloque el CSV real en `data/estaciones/camotan_insivumeh.csv` (columnas `fecha`, `precipitacion_mm`; mm/día). La interfaz **no** sube archivos.
4. Un archivo de reglas ausente o con JSON inválido solo desactiva estos endpoints (503 con motivo); el resto de la aplicación sigue funcionando.
5. Las reglas de este módulo no entran en el hash de las corridas del motor: cambiarlas no invalida corridas guardadas.

## 7. Pendientes de validación oficial y de campo
- **MAGA/ICTA:** confirmar ventanas de primera y postrera para Jocotán; ciclo y floración de ICTA B-9 y B-15; ciclos recomendados por variedad; Kc locales; umbrales hídricos con cita.
- **INSIVUMEH:** serie diaria 2001–2025 de la estación Camotán; procedimiento oficial del inicio de la época lluviosa.
- **Campo:** calibrar duraciones de etapas y Kc con observaciones locales.

## 8. Pruebas
`apps/api/tests/test_agronomy.py` (validación, ventanas y límites, umbrales, JSON ausente/mal formado/cambio sin tocar código, pentadas con huecos y años bisiestos, retraso, estación con CSV válido/incompleto/sucio, métricas exactas, ejemplo ficticio, mensajes es/en), `tests/integration/test_agronomy_api.py` (PostGIS real), `apps/web/src/components/zone/AgronomyValidation.test.tsx` y `tests/contract` (38 operaciones).
"""

ADR = """# ADR-023: Validación agronómica de Jocotán (reglas en JSON, inicio de lluvias sandbox y validación con estación)

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
"""

Path("docs/VALIDACION_AGRONOMICA_JOCOTAN.md").write_text(
    DOC.replace("__TABLE__", table).replace("__SOURCES__", sources), encoding="utf-8"
)
Path("docs/decisions/ADR-023-validacion-agronomica-jocotan.md").write_text(ADR, encoding="utf-8")
index = Path("docs/decisions/README.md")
text = index.read_text(encoding="utf-8")
row22 = "| [022](ADR-022-limite-municipal-y-seleccion-de-ubicacion.md) | Límite municipal y selección de ubicación | **propuesto** |"
if "ADR-023" not in text:
    text = text.replace(
        row22,
        row22
        + "\n| [023](ADR-023-validacion-agronomica-jocotan.md) | Validación agronómica de Jocotán (JSON, inicio de lluvias sandbox, estación) | **propuesto** |",
        1,
    )
    index.write_text(text, encoding="utf-8")
print("docs escritos")
