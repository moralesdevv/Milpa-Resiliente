"""Estimación SANDBOX del inicio de la época lluviosa por pentadas y comparación con la fecha de siembra.

Criterio (MAGA, Informe No. 6, 8-may-2025, con datos de INSIVUMEH e ICC, adaptado de Alfaro, Cid y Enfield 1999):
una pentada acumula al menos 25 mm y una o ambas de las dos pentadas consecutivas también; las pentadas
anterior y siguientes deben superar 0.5 mm. NO es el método metodológico oficial de INSIVUMEH y aquí se
aplica a precipitación satelital zonal. Los parámetros salen del JSON de reglas.

Los datos faltantes nunca se interpretan como lluvia cero: una pentada con algún día sin dato no es evaluable.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from api.agronomy.i18n import t

PENTADS_PER_YEAR = 73
SANDBOX_STATE = "Escenario Sandbox - No usar para decisiones operativas"
METHOD_LABEL = "Criterio de pentadas configurado (MAGA Informe 6/2025; experimental)"


def _as_series(data: Any) -> pd.Series:
    """Acepta Series, dict fecha→mm o lista de (fecha, mm); devuelve Series diaria ordenada sin duplicados."""
    if isinstance(data, pd.Series):
        series = data.copy()
    elif isinstance(data, Mapping | Sequence):
        series = pd.Series(dict(data))
    else:
        raise TypeError(
            "La precipitación debe ser una Serie, un diccionario o una lista de (fecha, mm)"
        )
    series.index = pd.to_datetime(series.index, errors="coerce")
    series = pd.to_numeric(series, errors="coerce")
    series = series.loc[series.index.notna()]
    series.index = pd.DatetimeIndex(series.index).normalize()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    cleaned: pd.Series = series.where(
        series >= 0
    )  # un valor negativo es inválido: se trata como faltante
    return cleaned


def _pentad_table(series: pd.Series, year: int, min_valid: int) -> list[dict[str, Any]]:
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    daily = series.reindex(days)
    # Pentadas por fecha de calendario (iguales en todos los años): en año bisiesto el 29-feb se suma a la pentada 12
    # y el resto de fechas conserva la misma pentada que en un año común.
    reference_doy = np.where(
        days.is_leap_year & (days.day_of_year >= 60), days.day_of_year - 1, days.day_of_year
    )
    pentad_of_day = (reference_doy - 1) // 5 + 1
    rows: list[dict[str, Any]] = []
    for k in range(1, PENTADS_PER_YEAR + 1):
        block = daily[pentad_of_day == k]
        valid = int(block.notna().sum())
        total = len(block)
        complete = valid >= max(min_valid, 1) and valid == total
        rows.append(
            {
                "pentada": k,
                "inicio": block.index[0].date().isoformat(),
                "fin": block.index[-1].date().isoformat(),
                "precipitacion_mm": round(float(block.sum()), 2) if complete else None,
                "dias_validos": valid,
                "dias_totales": total,
                "completa": complete,
            }
        )
    return rows


def _mm(row: dict[str, Any]) -> float | None:
    value = row["precipitacion_mm"]
    return None if value is None else float(value)


def detectar_inicio_lluvias(
    datos_precipitacion_diaria: Any,
    config: dict[str, Any],
    anio: int | None = None,
    fuente_precipitacion: str = "No indicada",
    idioma: str = "es",
) -> dict[str, Any]:
    series = _as_series(datos_precipitacion_diaria)
    differences = config.get("diferencias_respecto_al_oficial_en") if idioma == "en" else None
    limitaciones = [
        t("onset_limit_unofficial", idioma),
        t("onset_limit_pentads", idioma),
        *(differences or config.get("diferencias_respecto_al_oficial", [])),
    ]
    base: dict[str, Any] = {
        "fecha_estimada_inicio": None,
        "metodo": METHOD_LABEL,
        "precipitacion_pentadas": [],
        "estado": SANDBOX_STATE,
        "limitaciones": limitaciones,
        "fuente_precipitacion": fuente_precipitacion,
        "criterio": {
            "acumulado_minimo_mm": float(config["acumulado_minimo_mm"]),
            "persistencia": config.get("persistencia", {}).get(
                "modo", "al_menos_una_de_las_siguientes"
            ),
            "continuidad_minima_mm": float(config.get("continuidad_minima_mm", 0.5)),
            "fuente_criterio": config.get("fuente_criterio"),
        },
        "anio": anio,
        "resultado": "datos_insuficientes",
        "entradas": {
            "dias_con_dato": int(series.notna().sum()),
            "primer_dia": None,
            "ultimo_dia": None,
        },
    }
    if series.dropna().empty:
        base["limitaciones"].append(t("onset_no_data", idioma))
        return base
    valid_index = series.dropna().index
    base["entradas"]["primer_dia"] = valid_index.min().date().isoformat()
    base["entradas"]["ultimo_dia"] = valid_index.max().date().isoformat()
    if anio is None:
        anio = int(valid_index.max().year)
        base["anio"] = anio

    min_valid = int(config.get("dias_minimos_validos_por_pentada", 5))
    pentads = _pentad_table(series, anio, min_valid)
    base["precipitacion_pentadas"] = pentads

    threshold = float(config["acumulado_minimo_mm"])
    continuity = float(config.get("continuidad_minima_mm", 0.5))
    mode = str(config.get("persistencia", {}).get("modo", "al_menos_una_de_las_siguientes"))
    following = int(config.get("persistencia", {}).get("pentadas_siguientes", 2))
    start_md = str(config["busqueda"]["inicio_md"])
    end_md = str(config["busqueda"]["fin_md"])

    unevaluable = 0
    for k in range(1, PENTADS_PER_YEAR - following):
        row = pentads[k - 1]
        md = row["inicio"][5:]
        if not start_md <= md <= end_md or k < 2:
            continue
        window = [pentads[k - 2], row, *pentads[k : k + following]]
        values = [_mm(r) for r in window]
        if any(v is None for v in values):
            unevaluable += 1
            continue
        previous, current, nexts = values[0], values[1], values[2:]
        if previous is None or current is None:
            continue
        if current < threshold:
            continue
        reached = [v is not None and v >= threshold for v in nexts]
        persistence_ok = all(reached) if mode == "ambas_siguientes" else any(reached)
        continuity_ok = previous > continuity and all(
            v is not None and v > continuity for v in nexts
        )
        if persistence_ok and continuity_ok:
            base["fecha_estimada_inicio"] = row["inicio"]
            base["resultado"] = "detectado"
            base["pentada_inicio"] = k
            return base
    if unevaluable:
        base["limitaciones"].append(t("onset_unevaluable", idioma, count=unevaluable))
        base["resultado"] = "datos_insuficientes"
    else:
        base["limitaciones"].append(t("onset_none_met", idioma))
        base["resultado"] = "no_detectado"
    return base


def evaluar_retraso_adaptacion(
    fecha_estimada_inicio: date | str | None,
    fecha_siembra_usuario: date | str,
    umbral_retraso_dias: int = 15,
    idioma: str = "es",
) -> dict[str, Any]:
    note = t("delay_note", idioma)
    if fecha_estimada_inicio is None:
        return {
            "dias_diferencia": None,
            "advertencias": [],
            "conclusion": "sin_conclusion",
            "mensaje": t("delay_none", idioma),
            "nota": note,
        }
    onset = _to_date(fecha_estimada_inicio)
    sowing = _to_date(fecha_siembra_usuario)
    diff = (sowing - onset).days
    warnings: list[str] = []
    if diff < 0:
        warnings.append(t("delay_before", idioma, days=-diff))
        conclusion = "antes_del_inicio"
    elif diff > umbral_retraso_dias:
        warnings.append(t("delay_late", idioma, days=diff, limit=umbral_retraso_dias))
        conclusion = "retraso_mayor_al_umbral"
    else:
        conclusion = "dentro_del_rango"
    return {
        "dias_diferencia": diff,
        "advertencias": warnings,
        "conclusion": conclusion,
        "mensaje": note,
        "nota": note,
    }


def _to_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def finite(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)
