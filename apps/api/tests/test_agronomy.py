"""Validación agronómica, inicio de lluvias sandbox y validación con la estación Camotán.

Las series de lluvia de estas pruebas son SINTÉTICAS y existen solo para ejercitar el código; ninguna se
usa fuera de pruebas ni respalda conclusiones científicas.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from api.agronomy.onset import detectar_inicio_lluvias, evaluar_retraso_adaptacion
from api.agronomy.rules import RulesError, load_rules
from api.agronomy.station import LEVEL_B, LEVEL_C, validar_con_estacion_local
from api.agronomy.validation import validar_siembra

ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / "regions" / "reglas_agronomicas_jocotan.json"
EXAMPLE_CSV = ROOT / "data" / "estaciones" / "camotan_ejemplo.csv"


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES_PATH)


def check(rules, **kw):
    base = {
        "cultivo": "maiz",
        "variedad": "ICTA B-7",
        "fecha_siembra": date(2025, 5, 15),
        "ciclo": "primera",
    }
    return validar_siembra(rules, **{**base, **kw})


# ------------------------------------------------------------------ validación de siembra (1-7)
def test_valid_variety_returns_parameters_sources_and_provisional_state(rules):
    out = check(rules, dias_secos_recientes=2, lluvia_15_dias_mm=40.0)
    assert out["es_valido"] is True and out["alertas"] == []
    assert out["kc_etapa_media"] == 1.20
    assert out["parametros_fenologicos"]["ciclo_total_dias"] == 120
    assert "Provisional" in out["estado_validacion"] and out["fuentes"] and out["supuestos"]


def test_unknown_variety_is_rejected_with_the_allowed_list(rules):
    out = check(rules, variedad="ICTA Inventada")
    assert out["es_valido"] is False
    assert any("no está permitida" in a and "ICTA B-5" in a for a in out["alertas"])


def test_bean_variety_is_not_valid_for_maize_and_unknown_crop_is_controlled(rules):
    assert check(rules, variedad="ICTA Ostúa")["es_valido"] is False
    out = check(rules, cultivo="quinua")
    assert out["es_valido"] is False and "no configurado" in out["alertas"][0]


def test_date_inside_window_has_no_window_alert(rules):
    assert not any("ventana" in a for a in check(rules)["alertas"])


def test_date_outside_window_is_a_compatibility_alert_not_a_prohibition(rules):
    out = check(
        rules, fecha_siembra=date(2025, 7, 20), dias_secos_recientes=0, lluvia_15_dias_mm=50
    )
    assert out["es_valido"] is False
    assert any("fuera de la ventana" in a and "no una prohibición" in a for a in out["alertas"])
    assert (
        out["kc_etapa_media"] == 1.20
    )  # los parámetros se siguen entregando: el usuario puede continuar


@pytest.mark.parametrize(
    ("day", "ciclo", "inside"),
    [
        (date(2025, 5, 1), "primera", True),
        (date(2025, 6, 30), "primera", True),
        (date(2025, 4, 30), "primera", False),
        (date(2025, 7, 1), "primera", False),
        (date(2025, 8, 20), "postrera", True),
        (date(2025, 9, 30), "postrera", True),
        (date(2025, 8, 19), "postrera", False),
        (date(2025, 10, 1), "postrera", False),
    ],
)
def test_window_limits_are_inclusive(rules, day, ciclo, inside):
    out = check(rules, fecha_siembra=day, ciclo=ciclo)
    assert any("fuera de la ventana" in a for a in out["alertas"]) is (not inside)


def test_invalid_cycle_is_reported(rules):
    out = check(rules, ciclo="verano")
    assert any("Ciclo 'verano' no válido" in a for a in out["alertas"])


def test_dry_day_threshold_is_reached_or_exceeded_per_crop(rules):
    assert not any("sequía" in a for a in check(rules, dias_secos_recientes=9)["alertas"])
    assert any("sequía" in a for a in check(rules, dias_secos_recientes=10)["alertas"])
    beans = {"cultivo": "frijol", "variedad": "ICTA Ostúa"}
    assert not any("sequía" in a for a in check(rules, dias_secos_recientes=6, **beans)["alertas"])
    assert any("sequía" in a for a in check(rules, dias_secos_recientes=7, **beans)["alertas"])


def test_rain_below_the_15_day_minimum_raises_an_alert(rules):
    out = check(rules, lluvia_15_dias_mm=19.9)
    assert any("por debajo del mínimo" in a for a in out["alertas"])
    assert not any("por debajo" in a for a in check(rules, lluvia_15_dias_mm=20.0)["alertas"])


def test_missing_water_signals_are_warnings_not_zero(rules):
    out = check(rules)
    assert any("no se evaluó" in w for w in out["advertencias"])


def test_variety_without_documented_cycle_gets_a_limitation_not_an_assumption(rules):
    out = check(rules, variedad="ICTA B-9")
    assert any("No se encontró el ciclo" in w for w in out["advertencias"])
    assert out["parametros_fenologicos"]["ciclo_total_dias"] == 125  # proxy FAO-56, rotulado
    assert any(
        "No hay evidencia" in w
        for w in check(rules, ciclo="postrera", fecha_siembra=date(2025, 9, 1))["advertencias"]
    )


# ------------------------------------------------------------------ configuración (8-9)
def test_missing_rules_file_is_a_controlled_error(tmp_path):
    with pytest.raises(RulesError, match="No se pudo leer"):
        load_rules(tmp_path / "no_existe.json")


def test_malformed_and_incomplete_rules_are_controlled_errors(tmp_path):
    bad = tmp_path / "mal.json"
    bad.write_text("{no es json", encoding="utf-8")
    with pytest.raises(RulesError, match="no es JSON válido"):
        load_rules(bad)
    incomplete = tmp_path / "incompleto.json"
    incomplete.write_text(json.dumps({"estado_validacion": "x"}), encoding="utf-8")
    with pytest.raises(RulesError, match="ventanas_siembra"):
        load_rules(incomplete)


def test_planting_windows_change_from_the_json_without_touching_code(tmp_path):
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    data["ventanas_siembra"]["primera"]["fin"] = "07-15"
    path = tmp_path / "reglas.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    custom = load_rules(path)
    out = validar_siembra(custom, "maiz", "ICTA B-7", date(2025, 7, 10), "primera", 0, 50.0)
    assert not any("fuera de la ventana" in a for a in out["alertas"])


def test_phenology_stage_sums_match_the_total_cycle_for_every_variety(rules):
    totals: dict[tuple[str, str], int] = {}
    for row in rules.raw["parametros_fenologicos"]:
        key = (row["cultivo"], row["variedad"])
        totals[key] = totals.get(key, 0) + row["duracion_dias"]
        assert row["fuente"] and row["tipo_dato"] and row["confianza"]
    for crop, varieties in rules.raw["variedades"].items():
        for var in varieties:
            assert totals[(crop, var["nombre"])] == (var["ciclo_total_dias"] or 125), var["nombre"]


# ------------------------------------------------------------------ inicio de lluvias (10-14)
def synthetic_year(year: int, plan: dict[tuple[str, str], float]) -> pd.Series:
    """Serie diaria de PRUEBA: 0 mm salvo los rangos indicados (mm repartidos por día)."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    series = pd.Series(0.0, index=days)
    for (start, end), per_day in plan.items():
        series.loc[f"{year}-{start}" : f"{year}-{end}"] = per_day
    return series


def onset_config(rules):
    return rules.onset


def test_pentad_detection_finds_the_first_qualifying_pentad(rules):
    # pentadas desde el 1-ene: 11-may a 25-may = pentadas 27-29 con 6 mm/día (30 mm); el resto del año 1 mm/día
    series = synthetic_year(2025, {("01-01", "12-31"): 1.0, ("05-11", "05-25"): 6.0})
    out = detectar_inicio_lluvias(series, onset_config(rules), 2025, "SERIE DE PRUEBA")
    assert out["resultado"] == "detectado"
    assert out["fecha_estimada_inicio"] == "2025-05-11"
    assert (
        "Sandbox" in out["estado"]
        and out["limitaciones"]
        and out["fuente_precipitacion"] == "SERIE DE PRUEBA"
    )
    assert len(out["precipitacion_pentadas"]) == 73
    first = next(p for p in out["precipitacion_pentadas"] if p["inicio"] == "2025-05-11")
    assert first["precipitacion_mm"] == 30.0 and first["completa"]


def test_persistence_modes_differ_when_only_one_following_pentad_reaches_the_threshold(rules):
    series = synthetic_year(
        2025, {("01-01", "12-31"): 1.0, ("05-11", "05-15"): 6.0, ("05-16", "05-20"): 6.0}
    )
    cfg = onset_config(rules)
    assert (
        detectar_inicio_lluvias(series, cfg, 2025)["resultado"] == "detectado"
    )  # una de las dos siguientes
    strict = {**cfg, "persistencia": {**cfg["persistencia"], "modo": "ambas_siguientes"}}
    assert detectar_inicio_lluvias(series, strict, 2025)["resultado"] == "no_detectado"


def test_isolated_convective_burst_without_continuity_is_not_an_onset(rules):
    series = synthetic_year(2025, {("05-11", "05-15"): 6.0})  # una pentada de 30 mm y el resto 0
    assert detectar_inicio_lluvias(series, onset_config(rules), 2025)["resultado"] == "no_detectado"


def test_incomplete_precipitation_is_never_read_as_zero(rules):
    series = synthetic_year(2025, {("01-01", "12-31"): 1.0, ("05-11", "05-25"): 6.0})
    series.loc["2025-05-13"] = np.nan  # un día sin dato dentro de la primera pentada candidata
    out = detectar_inicio_lluvias(series, onset_config(rules), 2025)
    broken = next(p for p in out["precipitacion_pentadas"] if p["inicio"] == "2025-05-11")
    assert broken["precipitacion_mm"] is None and broken["completa"] is False
    assert out["fecha_estimada_inicio"] != "2025-05-11"
    empty = detectar_inicio_lluvias(pd.Series(dtype=float), onset_config(rules))
    assert empty["resultado"] == "datos_insuficientes" and empty["fecha_estimada_inicio"] is None


def test_no_detectable_onset_is_reported_without_inventing_a_date(rules):
    out = detectar_inicio_lluvias(
        synthetic_year(2025, {("01-01", "12-31"): 1.0}), onset_config(rules), 2025
    )
    assert out["resultado"] == "no_detectado" and out["fecha_estimada_inicio"] is None
    assert evaluar_retraso_adaptacion(None, date(2025, 6, 1))["conclusion"] == "sin_conclusion"


def test_sowing_before_the_estimated_onset_warns_about_seed_moisture():
    out = evaluar_retraso_adaptacion("2025-05-12", date(2025, 5, 5))
    assert out["dias_diferencia"] == -7 and out["conclusion"] == "antes_del_inicio"
    assert "falta de humedad" in out["advertencias"][0] and "no es una predicción" in out["nota"]


def test_sowing_more_than_15_days_after_the_onset_warns_about_the_growing_window():
    late = evaluar_retraso_adaptacion("2025-05-12", date(2025, 5, 28))
    assert late["dias_diferencia"] == 16 and late["conclusion"] == "retraso_mayor_al_umbral"
    assert "ventana de crecimiento" in late["advertencias"][0]
    assert (
        evaluar_retraso_adaptacion("2025-05-12", date(2025, 5, 27))["advertencias"] == []
    )  # 15 d exactos: sin aviso


# ------------------------------------------------------------------ estación Camotán (15-20)
def satellite_series(days: int = 400, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=days)
    return pd.Series(np.round(rng.gamma(0.6, 6.0, days), 1), index=index)


def write_csv(path: Path, series: pd.Series, header: str = "fecha,precipitacion_mm") -> Path:
    lines = [header] + [f"{d.date().isoformat()},{v}" for d, v in series.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_without_station_csv_the_state_is_level_c_pending():
    out = validar_con_estacion_local(satellite_series(), None)
    assert out["estado_validacion"] == "Nivel C - Pendiente" and out["metricas"] is None
    assert out["fuente_sugerida"] == "INSIVUMEH - Estación Camotán"
    assert "no han sido verificados localmente" in out["mensaje"]


def test_valid_station_csv_with_enough_days_reaches_level_b_with_metrics(tmp_path):
    sat = satellite_series()
    noise = np.random.default_rng(1).normal(0, 0.5, len(sat))
    station = (sat + noise).clip(lower=0).round(1)
    csv = write_csv(tmp_path / "estacion_real.csv", station)
    out = validar_con_estacion_local(
        sat, csv, {"min_observaciones_nivel_b": 365, "min_observaciones_correlacion": 30}
    )
    assert out["estado_validacion"] == LEVEL_B
    m = out["metricas"]
    assert m["n_comparados"] == 400 and m["correlacion_pearson"] > 0.9
    assert (
        m["unidades"] == "mm/día"
        and m["resolucion_temporal"] == "diaria"
        and "IMERG" in m["producto_evaluado"]
    )
    assert out["es_ejemplo_ficticio"] is False


def test_csv_with_missing_dates_compares_only_matching_days_and_stays_level_c_if_short(tmp_path):
    sat = satellite_series(120)
    partial = sat.iloc[10:60]  # la estación solo cubre 50 de 120 días
    csv = write_csv(tmp_path / "parcial.csv", partial)
    out = validar_con_estacion_local(
        sat, csv, {"min_observaciones_nivel_b": 365, "min_observaciones_correlacion": 30}
    )
    assert out["metricas"]["n_comparados"] == 50
    assert out["estado_validacion"] == LEVEL_C and "Nivel B" in out["mensaje"]


def test_csv_with_invalid_values_counts_and_excludes_them(tmp_path):
    sat = satellite_series(40)
    path = tmp_path / "sucio.csv"
    path.write_text(
        "fecha,precipitacion_mm\n2024-01-01,1.0\n2024-01-02,abc\n2024-01-03,-5\nno-fecha,2.0\n2024-01-05,\n2024-01-06,3.0\n2024-01-06,9.0\n",
        encoding="utf-8",
    )
    out = validar_con_estacion_local(sat, path, {"min_observaciones_correlacion": 30})
    rows = out["filas"]
    assert (
        rows["valor_no_numerico"] == 1
        and rows["valor_negativo"] == 1
        and rows["fecha_invalida"] == 1
    )
    assert rows["fechas_duplicadas"] == 1 and rows["validas"] == 2
    assert (
        out["metricas"]["correlacion_pearson"] is None
        and "Muestra insuficiente" in out["metricas"]["motivo_sin_correlacion"]
    )
    assert out["estado_validacion"] == LEVEL_C


def test_wrong_columns_and_missing_file_are_controlled(tmp_path):
    bad = tmp_path / "columnas.csv"
    bad.write_text("date,rain\n2024-01-01,1\n", encoding="utf-8")
    assert "columnas" in validar_con_estacion_local(satellite_series(), bad)["mensaje"]
    assert (
        validar_con_estacion_local(satellite_series(), tmp_path / "x.csv")["estado_validacion"]
        == LEVEL_C
    )


def test_rmse_bias_and_correlation_are_computed_exactly(tmp_path):
    index = pd.date_range("2024-01-01", periods=5)
    sat = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=index)
    station = pd.Series([2.0, 2.0, 4.0, 4.0, 6.0], index=index)  # sat - est = -1, 0, -1, 0, -1
    out = validar_con_estacion_local(
        sat,
        write_csv(tmp_path / "e.csv", station),
        {"min_observaciones_nivel_b": 5, "min_observaciones_correlacion": 5},
    )
    m = out["metricas"]
    assert m["sesgo_mm_dia"] == pytest.approx(-0.6)
    assert m["rmse_mm_dia"] == pytest.approx(np.sqrt(3 / 5), abs=1e-4)
    assert m["correlacion_pearson"] == pytest.approx(
        float(np.corrcoef(sat, station)[0, 1]), abs=1e-4
    )
    assert out["estado_validacion"] == LEVEL_B  # umbral de la prueba reducido a 5 días


def test_constant_series_has_no_correlation(tmp_path):
    index = pd.date_range("2024-01-01", periods=40)
    sat = pd.Series(np.arange(40, dtype=float), index=index)
    out = validar_con_estacion_local(
        sat,
        write_csv(tmp_path / "c.csv", pd.Series(1.0, index=index)),
        {"min_observaciones_nivel_b": 10},
    )
    assert out["metricas"]["correlacion_pearson"] is None and out["estado_validacion"] == LEVEL_C


def test_the_fictitious_example_csv_never_changes_the_level(tmp_path):
    sat = pd.Series(
        [1.0, 0.0, 8.0], index=pd.to_datetime(["2025-05-01", "2025-05-02", "2025-05-03"])
    )
    out = validar_con_estacion_local(
        sat, EXAMPLE_CSV, {"min_observaciones_nivel_b": 1, "min_observaciones_correlacion": 1}
    )
    assert (
        out["estado_validacion"] == LEVEL_C
        and out["es_ejemplo_ficticio"] is True
        and out["metricas"] is None
    )
    # aunque se copie con otro nombre, la marca de datos ficticios dentro del archivo lo sigue identificando
    copy = tmp_path / "estacion_real.csv"
    shutil.copy(EXAMPLE_CSV, copy)
    assert (
        validar_con_estacion_local(sat, copy, {"min_observaciones_nivel_b": 1})["estado_validacion"]
        == LEVEL_C
    )
    assert "FICTICIOS" in EXAMPLE_CSV.read_text(encoding="utf-8")


def test_station_csv_example_dates_are_valid_iso(tmp_path):
    frame = pd.read_csv(EXAMPLE_CSV, comment="#")
    assert list(frame.columns) == ["fecha", "precipitacion_mm"]
    assert all(date.fromisoformat(d) for d in frame["fecha"]) and timedelta(0) == timedelta(0)


# ------------------------------------------------------------------ idioma
def test_every_message_exists_in_spanish_and_english():
    from api.agronomy.i18n import MSG

    for key, entry in MSG.items():
        assert entry["es"].strip() and entry["en"].strip(), key
        # los marcadores de formato deben coincidir en ambos idiomas
        import string

        fields = lambda text: {f for _, f, _, _ in string.Formatter().parse(text) if f}  # noqa: E731
        assert fields(entry["es"]) == fields(entry["en"]), key


def test_english_output_for_validation_onset_delay_and_station(rules):
    out = check(
        rules,
        fecha_siembra=date(2025, 7, 20),
        dias_secos_recientes=12,
        lluvia_15_dias_mm=5,
        idioma="en",
    )
    assert any(
        "outside the configured planting window" in a and "not a prohibition" in a
        for a in out["alertas"]
    )
    assert any("Drought alert" in a for a in out["alertas"]) and any(
        "below the configured minimum" in a for a in out["alertas"]
    )
    assert out["senal_sequia"] is True and out["fecha_en_ventana"] is False
    assert out["supuestos"][0].startswith("The Kc values are FAO-56")
    assert out["parametros_fenologicos"]["etapas"][0]["supuesto_aplicado"].startswith(
        "Cycle of 4 months"
    )
    assert (
        "falta de humedad"
        not in evaluar_retraso_adaptacion("2025-05-12", date(2025, 5, 5), idioma="en")[
            "advertencias"
        ][0]
    )
    assert (
        "No Camotán station data" in validar_con_estacion_local(None, None, idioma="en")["mensaje"]
    )
    onset = detectar_inicio_lluvias(pd.Series(dtype=float), rules.onset, idioma="en")
    assert any("no precipitation data" in x.lower() for x in onset["limitaciones"])


def test_pentads_are_fixed_by_calendar_date_also_in_leap_years(rules):
    for year, feb_days in ((2025, 5), (2024, 6)):
        out = detectar_inicio_lluvias(
            synthetic_year(year, {("01-01", "12-31"): 1.0}), onset_config(rules), year
        )
        table = out["precipitacion_pentadas"]
        assert len(table) == 73
        assert next(p for p in table if p["pentada"] == 12)["dias_totales"] == feb_days
        assert next(p for p in table if p["pentada"] == 27)["inicio"] == f"{year}-05-11"
        assert sum(p["dias_totales"] for p in table) == (366 if year == 2024 else 365)
