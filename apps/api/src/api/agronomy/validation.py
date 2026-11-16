"""Validación agronómica de una siembra (cultivo, variedad, ciclo, fecha, señales hídricas).

Función pura: recibe las reglas ya cargadas y devuelve un diccionario estructurado. No lee archivos ni la
red. Una fecha fuera de la ventana es una advertencia de compatibilidad con el calendario configurado, no
una prohibición ni una afirmación de imposibilidad agronómica.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from api.agronomy.i18n import t
from api.agronomy.rules import Rules, norm

NOT_DOCUMENTED = ("no documentado", "no verificado")


def _in_window(day: date, window: dict[str, Any]) -> bool:
    return str(window["inicio"]) <= day.strftime("%m-%d") <= str(window["fin"])


def _phenology_summary(rows: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    return {
        "etapas": [_row(r, lang) for r in rows],
        "ciclo_total_dias": sum(int(r["duracion_dias"]) for r in rows) if rows else None,
        "nota": "Duraciones derivadas o proxy FAO-56; calibrar con observaciones locales."
        if lang == "es"
        else "Durations are derived or FAO-56 proxies; calibrate with local observations.",
    }


def _row(row: dict[str, Any], lang: str) -> dict[str, Any]:
    out = dict(row)
    if lang == "en" and row.get("supuesto_aplicado_en"):
        out["supuesto_aplicado"] = row["supuesto_aplicado_en"]
    return out


def _water_checks(
    rules: Rules,
    crop: dict[str, Any],
    dias_secos_recientes: int | None,
    lluvia_15_dias_mm: float | None,
    temperatura_media_c: float | None,
    lang: str,
) -> tuple[list[str], list[str], bool]:
    """Umbrales hídricos y de temperatura del cultivo (parámetros del JSON, nunca fijos en el código)."""
    limits = crop["umbrales_hidricos"]
    alerts: list[str] = []
    warnings: list[str] = []
    drought = False
    max_dry = int(limits["dias_secos_consecutivos_riesgo"])
    if dias_secos_recientes is None:
        warnings.append(t("dry_missing", lang))
    elif dias_secos_recientes < 0:
        alerts.append(t("dry_negative", lang))
    elif dias_secos_recientes >= max_dry:
        drought = True
        alerts.append(
            t(
                "dry_alert",
                lang,
                days=dias_secos_recientes,
                limit=max_dry,
                mm=limits["lluvia_minima_mm_dia"],
            )
        )
    minimum = limits.get("lluvia_minima_15_dias_mm")
    if minimum is not None:
        if lluvia_15_dias_mm is None:
            warnings.append(t("rain_missing", lang))
        elif lluvia_15_dias_mm < 0:
            alerts.append(t("rain_negative", lang))
        elif lluvia_15_dias_mm < float(minimum):
            drought = True
            alerts.append(
                t("rain_low", lang, rain=f"{lluvia_15_dias_mm:.1f}", minimum=f"{float(minimum):g}")
            )
    elif lluvia_15_dias_mm is not None:
        warnings.append(t("rain_no_threshold", lang, crop=crop["nombre"]))
    temp = rules.raw.get("temperatura_siembra")
    if temperatura_media_c is not None and temp:
        low, high = float(temp["media_min_c"]), float(temp["media_max_c"])
        if not low <= temperatura_media_c <= high:
            alerts.append(
                t(
                    "temperature_out",
                    lang,
                    value=f"{temperatura_media_c:.1f}",
                    low=f"{low:g}",
                    high=f"{high:g}",
                )
            )
    return alerts, warnings, drought


def validar_siembra(
    rules: Rules,
    cultivo: str,
    variedad: str,
    fecha_siembra: date,
    ciclo: str,
    dias_secos_recientes: int | None = None,
    lluvia_15_dias_mm: float | None = None,
    temperatura_media_c: float | None = None,
    idioma: str = "es",
) -> dict[str, Any]:
    alertas: list[str] = []
    advertencias: list[str] = []
    fuentes_ids: list[str] = []

    key = rules.crop_key(cultivo)
    if key is None:
        crops = ", ".join(str(b.get("nombre", k)) for k, b in rules.raw["cultivos"].items())
        alertas.append(t("crop_unknown", idioma, value=cultivo, options=crops))
        return _result(
            rules,
            idioma,
            False,
            alertas,
            advertencias,
            cultivo,
            variedad,
            ciclo,
            fecha_siembra,
            None,
            None,
            [],
            [],
        )

    crop = rules.crop(key)
    var = rules.variety(key, variedad)
    if var is None:
        allowed = ", ".join(str(v["nombre"]) for v in rules.varieties(key))
        alertas.append(
            t("variety_not_allowed", idioma, value=variedad, crop=crop["nombre"], options=allowed)
        )
    else:
        fuentes_ids += [str(s) for s in var.get("fuentes", [])]
        if str(var.get("tipo_dato", "")).startswith("NO ENCONTRADO"):
            advertencias.append(t("variety_no_cycle", idioma, variety=var["nombre"]))

    window = rules.window(ciclo)
    in_window: bool | None = None
    if window is None:
        alertas.append(t("cycle_invalid", idioma, value=ciclo, options=", ".join(rules.cycles)))
    else:
        fuentes_ids += [str(s) for s in window.get("fuentes", [])]
        in_window = _in_window(fecha_siembra, window)
        if not in_window:
            others = [c for c in rules.cycles if norm(c) != norm(ciclo)]
            hint = next(
                (
                    t("window_hint", idioma, cycle=c)
                    for c in others
                    if _in_window(fecha_siembra, rules.window(c) or {})
                ),
                "",
            )
            alertas.append(
                t(
                    "outside_window",
                    idioma,
                    cycle=window["ciclo"],
                    start=window["inicio"],
                    end=window["fin"],
                    hint=hint,
                )
            )
        if var is not None:
            documented = str(var.get("ciclos_documentados", {}).get(window["ciclo"], ""))
            if documented.startswith(NOT_DOCUMENTED) or not documented:
                advertencias.append(
                    t("cycle_not_documented", idioma, variety=var["nombre"], cycle=window["ciclo"])
                )

    fuentes_ids.append(str(crop.get("umbral_basis", "USUARIO_SANDBOX")))
    water_alerts, water_warnings, drought = _water_checks(
        rules, crop, dias_secos_recientes, lluvia_15_dias_mm, temperatura_media_c, idioma
    )
    alertas += water_alerts
    advertencias += water_warnings

    rows = rules.phenology(key, var["nombre"]) if var else []
    fuentes_ids += [str(s) for row in rows for s in row.get("fuente", [])]
    result = _result(
        rules,
        idioma,
        not alertas,
        alertas,
        advertencias,
        crop["nombre"],
        str(var["nombre"]) if var else variedad,
        window["ciclo"] if window else ciclo,
        fecha_siembra,
        float(crop["kc_etapa_media"]),
        _phenology_summary(rows, idioma) if var else None,
        list(dict.fromkeys(fuentes_ids)),
        [
            crop["umbrales_hidricos"],
            {"estado": "Umbrales provisionales (USUARIO_SANDBOX), sin cita agronómica"},
        ],
    )
    result["fecha_en_ventana"] = in_window
    result["senal_sequia"] = drought
    return result


def _result(
    rules: Rules,
    lang: str,
    valid: bool,
    alertas: list[str],
    advertencias: list[str],
    cultivo: str,
    variedad: str,
    ciclo: str,
    fecha: date,
    kc_mid: float | None,
    phenology: dict[str, Any] | None,
    source_ids: list[str],
    thresholds: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "es_valido": valid,
        "alertas": alertas,
        "advertencias": advertencias,
        "cultivo": cultivo,
        "variedad": variedad,
        "ciclo": ciclo,
        "fecha_siembra": fecha.isoformat(),
        "kc_etapa_media": kc_mid,
        "parametros_fenologicos": phenology,
        "umbrales_aplicados": thresholds,
        "estado_validacion": rules.estado_for(lang),
        "fuentes": rules.sources(source_ids, lang),
        "supuestos": rules.supuestos_for(lang),
        "fecha_en_ventana": None,
        "senal_sequia": False,
    }
