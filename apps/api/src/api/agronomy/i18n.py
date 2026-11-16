"""Mensajes de la validación agronómica en español (por defecto, contrato del API) e inglés (interfaz).

Solo se traducen los mensajes generados por el código; los nombres de variedades, fuentes y valores del JSON de
reglas no cambian. Una clave inexistente es un error de programación y falla de forma visible en pruebas.
"""

from __future__ import annotations

from typing import Any

LANGS = ("es", "en")

MSG: dict[str, dict[str, str]] = {
    "crop_unknown": {
        "es": "Cultivo '{value}' no configurado; opciones: {options}.",
        "en": "Crop '{value}' is not configured; options: {options}.",
    },
    "variety_not_allowed": {
        "es": "La variedad '{value}' no está permitida para {crop}; opciones: {options}.",
        "en": "Variety '{value}' is not allowed for {crop}; options: {options}.",
    },
    "variety_no_cycle": {
        "es": "No se encontró el ciclo de {variety} en fuentes de ICTA; los parámetros de etapas son una referencia FAO-56, no una medición de la variedad.",
        "en": "No cycle length for {variety} was found in ICTA sources; the stage parameters are an FAO-56 reference, not a measurement of the variety.",
    },
    "cycle_invalid": {
        "es": "Ciclo '{value}' no válido; opciones: {options}.",
        "en": "Cycle '{value}' is not valid; options: {options}.",
    },
    "window_hint": {
        "es": " Coincide con la ventana de {cycle}.",
        "en": " It matches the {cycle} window.",
    },
    "outside_window": {
        "es": "Fecha fuera de la ventana de siembra configurada para {cycle} ({start} a {end}, provisional).{hint} Es una advertencia de compatibilidad con el calendario de referencia, no una prohibición.",
        "en": "Date is outside the configured planting window for {cycle} ({start} to {end}, provisional).{hint} This is a compatibility notice against the reference calendar, not a prohibition.",
    },
    "cycle_not_documented": {
        "es": "No hay evidencia en las fuentes consultadas de que {variety} esté recomendada para el ciclo {cycle}.",
        "en": "The consulted sources give no evidence that {variety} is recommended for the {cycle} cycle.",
    },
    "dry_missing": {
        "es": "No se indicaron días secos recientes: el umbral de sequía no se evaluó.",
        "en": "No recent dry days were given: the drought threshold was not evaluated.",
    },
    "dry_negative": {
        "es": "Los días secos recientes no pueden ser negativos.",
        "en": "Recent dry days cannot be negative.",
    },
    "dry_alert": {
        "es": "Alerta de sequía: {days} días secos consecutivos alcanzan o superan el umbral de riesgo configurado de {limit} días (lluvia diaria < {mm} mm).",
        "en": "Drought alert: {days} consecutive dry days reach or exceed the configured risk threshold of {limit} days (daily rain < {mm} mm).",
    },
    "rain_missing": {
        "es": "No se indicó la lluvia acumulada en 15 días: ese umbral no se evaluó.",
        "en": "Rainfall over 15 days was not given: that threshold was not evaluated.",
    },
    "rain_negative": {
        "es": "La lluvia acumulada no puede ser negativa.",
        "en": "Accumulated rainfall cannot be negative.",
    },
    "rain_low": {
        "es": "Lluvia acumulada en 15 días ({rain} mm) por debajo del mínimo configurado de {minimum} mm: riesgo para la germinación.",
        "en": "Rainfall over 15 days ({rain} mm) is below the configured minimum of {minimum} mm: germination risk.",
    },
    "rain_no_threshold": {
        "es": "No hay umbral de lluvia a 15 días configurado para {crop}; el dato se informa pero no se evaluó.",
        "en": "No 15-day rainfall threshold is configured for {crop}; the value is reported but not evaluated.",
    },
    "temperature_out": {
        "es": "Temperatura media de {value} °C fuera del rango configurado ({low}-{high} °C) para la fecha de siembra.",
        "en": "Mean temperature of {value} °C is outside the configured range ({low}-{high} °C) for the planting date.",
    },
    "insufficient_zone_data": {
        "es": "Datos climáticos insuficientes: hay {available} de {days} días de lluvia en la serie zonal para esa fecha; la serie es histórica y no es un pronóstico.",
        "en": "Insufficient climate data: {available} of {days} rainfall days are in the zonal series for that date; the series is historical, not a forecast.",
    },
    "no_temperature": {
        "es": "No hay temperatura POWER completa para la fecha de siembra; no se evaluó ese umbral.",
        "en": "There is no complete POWER temperature for the planting date; that threshold was not evaluated.",
    },
    "origin_declared": {
        "es": "datos declarados por el usuario",
        "en": "data declared by the user",
    },
    "origin_zonal": {
        "es": "serie histórica zonal (no es pronóstico)",
        "en": "zonal historical series (not a forecast)",
    },
    "rec_drought": {
        "es": "Hay una señal hídrica de riesgo con los umbrales provisionales; considere ajustar la fecha o consultar a extensión agrícola. No es una prohibición ni una predicción de pérdida de cosecha.",
        "en": "There is a water-risk signal under the provisional thresholds; consider adjusting the date or consulting agricultural extension. It is not a prohibition or a prediction of crop loss.",
    },
    "rec_ok": {
        "es": "La fecha cumple las reglas provisionales configuradas; confirme la decisión con el pronóstico local y asistencia técnica.",
        "en": "The date meets the configured provisional rules; confirm the decision with the local forecast and technical assistance.",
    },
    "rec_insufficient": {
        "es": "No hay evidencia suficiente para recomendar esta fecha; revise la cobertura climática o indique sus datos de lluvia.",
        "en": "There is not enough evidence to recommend this date; check the climate coverage or enter your own rainfall data.",
    },
    "rec_review": {
        "es": "Revise las alertas: indican compatibilidad con un calendario de referencia provisional, no una decisión.",
        "en": "Review the alerts: they indicate compatibility with a provisional reference calendar, not a decision.",
    },
    "delay_note": {
        "es": "Comparación temporal entre dos fechas; no es una predicción de pérdida de cosecha.",
        "en": "A comparison of two dates; it is not a prediction of crop loss.",
    },
    "delay_none": {
        "es": "No se detectó un inicio de lluvias confiable; no se generan conclusiones automáticas sobre el retraso.",
        "en": "No reliable rainy-season onset was detected; no automatic conclusion about delay is produced.",
    },
    "delay_before": {
        "es": "La siembra ocurre {days} día(s) antes del inicio estimado de lluvias: la semilla puede quedar expuesta a falta de humedad.",
        "en": "Sowing happens {days} day(s) before the estimated rainy-season onset: the seed may be exposed to a lack of moisture.",
    },
    "delay_late": {
        "es": "La siembra ocurre {days} días después del inicio estimado (más de {limit}): podría reducirse la ventana de crecimiento.",
        "en": "Sowing happens {days} days after the estimated onset (more than {limit}): the growing window could be shortened.",
    },
    "onset_limit_unofficial": {
        "es": "No es el método oficial de INSIVUMEH ni un boletín: es una estimación sandbox con precipitación satelital zonal.",
        "en": "This is not INSIVUMEH's official method or a bulletin: it is a sandbox estimate from zonal satellite precipitation.",
    },
    "onset_limit_pentads": {
        "es": "Las pentadas se fijan por fecha de calendario desde el 1 de enero; en años bisiestos el 29 de febrero se suma a la pentada 12.",
        "en": "Pentads are fixed by calendar date from 1 January; in leap years 29 February is added to pentad 12.",
    },
    "onset_no_data": {
        "es": "No hay datos de precipitación; no se puede estimar el inicio.",
        "en": "There is no precipitation data; the onset cannot be estimated.",
    },
    "onset_unevaluable": {
        "es": "{count} pentada(s) candidatas no se pudieron evaluar por días sin dato; no se rellenan con cero.",
        "en": "{count} candidate pentad(s) could not be evaluated because of days without data; gaps are never filled with zero.",
    },
    "onset_none_met": {
        "es": "Ninguna pentada de la ventana de búsqueda cumplió el criterio configurado.",
        "en": "No pentad in the search window met the configured criterion.",
    },
    "st_no_csv": {
        "es": "No se han cargado datos de la estación Camotán. Los datos satelitales IMERG/POWER no han sido verificados localmente.",
        "en": "No Camotán station data have been loaded. The IMERG/POWER satellite data have not been verified locally.",
    },
    "st_missing_file": {
        "es": "El archivo de la estación Camotán no existe; los datos satelitales siguen sin verificación local.",
        "en": "The Camotán station file does not exist; the satellite data remain without local verification.",
    },
    "st_too_big": {
        "es": "El CSV de la estación supera el tamaño máximo permitido y no se procesó.",
        "en": "The station CSV exceeds the maximum size and was not processed.",
    },
    "st_unreadable": {
        "es": "No se pudo procesar el CSV de la estación: {reason}",
        "en": "The station CSV could not be processed: {reason}",
    },
    "st_example": {
        "es": "El archivo es un ejemplo con datos ficticios para probar el formato: no se usa para validar y el estado se conserva.",
        "en": "The file is an example with fictitious data for testing the format: it is not used to validate and the status is kept.",
    },
    "st_empty": {
        "es": "El CSV no contiene filas válidas.",
        "en": "The CSV contains no valid rows.",
    },
    "st_no_satellite": {
        "es": "No hay datos satelitales con los que comparar.",
        "en": "There are no satellite data to compare with.",
    },
    "st_level_b": {
        "es": "Producto y periodo evaluados validados localmente con {n} días coincidentes. No valida otros productos ni periodos.",
        "en": "The evaluated product and period were validated locally with {n} matching days. It does not validate other products or periods.",
    },
    "st_level_c": {
        "es": "No se alcanza el Nivel B: {reason}.",
        "en": "Level B is not reached: {reason}.",
    },
    "st_need_days": {
        "es": "se requieren al menos {minimum} días coincidentes y n={n}",
        "en": "at least {minimum} matching days are required and n={n}",
    },
    "st_small_sample": {
        "es": "Muestra insuficiente (n={n} < {minimum})",
        "en": "Insufficient sample (n={n} < {minimum})",
    },
    "st_no_variance": {
        "es": "Una de las series no tiene variabilidad",
        "en": "One of the series has no variability",
    },
}


def t(key: str, lang: str = "es", **kwargs: Any) -> str:
    entry = MSG[key]
    return entry[lang if lang in entry else "es"].format(**kwargs)
