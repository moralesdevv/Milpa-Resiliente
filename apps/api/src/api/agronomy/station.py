"""Validación de la precipitación satelital contra la estación local Camotán (INSIVUMEH).

Por defecto NO hay datos de estación: el estado es «Nivel C - Pendiente». Solo una serie real de estación,
con suficientes observaciones coincidentes, puede pasar el estado a «Nivel B - Validado localmente»; eso
significa validación del producto y del periodo evaluados, no de todo el sistema. El CSV de ejemplo
(ficticio) nunca cambia el estado.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

import pandas as pd

from api.agronomy.i18n import t

LEVEL_C = "Nivel C - Pendiente"
LEVEL_B = "Nivel B - Validado localmente"
SUGGESTED_SOURCE = "INSIVUMEH - Estación Camotán"
FICTITIOUS_MARKERS = ("ficticio", "ficticios", "ejemplo")
MAX_CSV_BYTES = 20 * 1024 * 1024


def _pending(message: str, **extra: Any) -> dict[str, Any]:
    return {
        "estado_validacion": LEVEL_C,
        "mensaje": message,
        "metricas": None,
        "fuente_sugerida": SUGGESTED_SOURCE,
        **extra,
    }


def _is_fictitious(text: str, name: str) -> bool:
    head = "\n".join(
        line for line in text.splitlines()[:6] if line.lstrip().startswith("#")
    ).casefold()
    return any(m in head for m in FICTITIOUS_MARKERS) or any(
        m in name.casefold() for m in ("ejemplo", "ficticio")
    )


def parse_station_csv(text: str) -> tuple[pd.Series, dict[str, int]]:
    """Lee `fecha,precipitacion_mm` (líneas '#' = comentarios). Devuelve la serie válida y los conteos."""
    frame = pd.read_csv(io.StringIO(text), comment="#", dtype=str, skip_blank_lines=True)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if not {"fecha", "precipitacion_mm"} <= set(frame.columns):
        raise ValueError(
            "El CSV debe tener las columnas 'fecha' y 'precipitacion_mm' / The CSV needs the columns 'fecha' and 'precipitacion_mm'"
        )
    dates = pd.to_datetime(frame["fecha"].str.strip(), format="%Y-%m-%d", errors="coerce")
    values = pd.to_numeric(frame["precipitacion_mm"].str.strip(), errors="coerce")
    bad_date = int(dates.isna().sum())
    missing_value = int((values.isna() & frame["precipitacion_mm"].isna()).sum())
    bad_value = int((values.isna() & ~frame["precipitacion_mm"].isna()).sum())
    negative = int((values < 0).sum())
    ok = dates.notna() & values.notna() & (values >= 0)
    series = pd.Series(values[ok].to_numpy(dtype=float), index=pd.DatetimeIndex(dates[ok]))
    duplicated = int(series.index.duplicated(keep="first").sum())
    series = series[~series.index.duplicated(keep="first")].sort_index()
    counts = {
        "filas": len(frame),
        "validas": len(series),
        "fecha_invalida": bad_date,
        "valor_faltante": missing_value,
        "valor_no_numerico": bad_value,
        "valor_negativo": negative,
        "fechas_duplicadas": duplicated,
    }
    return series, counts


def metrics(
    satellite: pd.Series, station: pd.Series, min_corr_obs: int, lang: str = "es"
) -> dict[str, Any]:
    joined = pd.concat({"sat": satellite, "est": station}, axis=1, join="inner").dropna()
    n = len(joined)
    out: dict[str, Any] = {
        "n_comparados": n,
        "rmse_mm_dia": None,
        "sesgo_mm_dia": None,
        "correlacion_pearson": None,
        "periodo": None,
        "motivo_sin_correlacion": None,
    }
    if n == 0:
        return out
    diff = joined["sat"] - joined["est"]
    out["rmse_mm_dia"] = round(float(math.sqrt(float((diff**2).mean()))), 4)
    out["sesgo_mm_dia"] = round(float(diff.mean()), 4)
    out["periodo"] = {
        "desde": joined.index.min().date().isoformat(),
        "hasta": joined.index.max().date().isoformat(),
    }
    if n < min_corr_obs:
        out["motivo_sin_correlacion"] = t("st_small_sample", lang, n=n, minimum=min_corr_obs)
    elif joined["sat"].std(ddof=0) == 0 or joined["est"].std(ddof=0) == 0:
        out["motivo_sin_correlacion"] = t("st_no_variance", lang)
    else:
        out["correlacion_pearson"] = round(float(joined["sat"].corr(joined["est"])), 4)
    return out


def _read_station(
    path: Path, lang: str
) -> tuple[pd.Series | None, dict[str, int] | None, dict[str, Any] | None]:
    """Lee el CSV; devuelve (serie, conteos, respuesta_pendiente_si_no_se_puede_usar)."""
    if not path.is_file():
        return None, None, _pending(t("st_missing_file", lang))
    if path.stat().st_size > MAX_CSV_BYTES:
        return None, None, _pending(t("st_too_big", lang))
    try:
        text = path.read_text(encoding="utf-8-sig")
        station, counts = parse_station_csv(text)
    except (UnicodeDecodeError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return None, None, _pending(t("st_unreadable", lang, reason=exc))
    if _is_fictitious(text, path.name):
        return None, counts, _pending(t("st_example", lang), filas=counts, es_ejemplo_ficticio=True)
    if station.empty:
        return None, counts, _pending(t("st_empty", lang), filas=counts)
    return station, counts, None


def validar_con_estacion_local(
    datos_satelite: pd.Series | None,
    archivo_csv_estacion: Path | str | None = None,
    config: dict[str, Any] | None = None,
    producto_satelital: str = "GPM IMERG Final V07B (precipitación diaria)",
    idioma: str = "es",
) -> dict[str, Any]:
    cfg = config or {}
    min_b = int(cfg.get("min_observaciones_nivel_b", 365))
    min_corr = int(cfg.get("min_observaciones_correlacion", 30))
    if archivo_csv_estacion is None:
        return _pending(t("st_no_csv", idioma))
    station, counts, early = _read_station(Path(archivo_csv_estacion), idioma)
    if early is not None:
        return early
    if station is None or datos_satelite is None or datos_satelite.dropna().empty:
        return _pending(t("st_no_satellite", idioma), filas=counts)

    result = metrics(datos_satelite.dropna(), station, min_corr, idioma)
    result.update(
        {
            "producto_evaluado": producto_satelital,
            "unidades": "mm/día",
            "resolucion_temporal": "diaria",
            "dias_estacion_validos": len(station),
            "dias_satelite_validos": int(datos_satelite.dropna().shape[0]),
        }
    )
    n = result["n_comparados"]
    if n >= min_b and result["correlacion_pearson"] is not None:
        state = LEVEL_B
        message = t("st_level_b", idioma, n=n)
    else:
        reason = result["motivo_sin_correlacion"] or t("st_need_days", idioma, minimum=min_b, n=n)
        state, message = LEVEL_C, t("st_level_c", idioma, reason=reason)
    return {
        "estado_validacion": state,
        "mensaje": message,
        "metricas": result,
        "fuente_sugerida": SUGGESTED_SOURCE,
        "filas": counts,
        "es_ejemplo_ficticio": False,
    }
