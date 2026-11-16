"""Endpoints agronómicos contra PostgreSQL/PostGIS real: opciones, validación de siembra, inicio de lluvias y
estado de validación con la estación Camotán.

La serie climática de estas pruebas es SINTÉTICA y está aislada en un directorio temporal; los parámetros
agronómicos son los del JSON real del repositorio.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.adapters.not_integrated import default_ports
from api.jobs.dispatch import NullDispatcher
from api.main import create_app
from testkit import ROOT
from testkit.app import World, make_settings

RULES = ROOT / "regions" / "reglas_agronomicas_jocotan.json"
EXAMPLE = ROOT / "data" / "estaciones" / "camotan_ejemplo.csv"
ZONE_WKT = "POLYGON((-89.40 14.80, -89.30 14.80, -89.30 14.90, -89.40 14.90, -89.40 14.80))"


@pytest.fixture
def agro_zone(admin_engine: Engine) -> str:
    with admin_engine.begin() as c:
        region = c.execute(
            text(
                "INSERT INTO geo.region (code, name, config_uri, config_hash, bbox) VALUES "
                "('AGR', 'Región agronómica', 'test://agro', repeat('0',64), ST_GeomFromText(:g,4326)) "
                "RETURNING region_id"
            ),
            {"g": ZONE_WKT},
        ).scalar_one()
        zone = c.execute(
            text(
                "INSERT INTO geo.zone (region_id, name, geom) VALUES (:r, 'camotan_jocotan', "
                "ST_Multi(ST_GeomFromText(:g,4326))) RETURNING zone_id"
            ),
            {"r": region, "g": ZONE_WKT},
        ).scalar_one()
    return str(zone)


def synthetic_daily() -> pd.DataFrame:
    """2024: 1 mm/día salvo 6 mm/día del 11 al 25 de mayo (pentadas 27-29 con 30 mm). SINTÉTICA."""
    days = pd.date_range("2024-01-01", "2024-12-31")
    rain = pd.Series(1.0, index=days)
    rain.loc["2024-05-11":"2024-05-25"] = 6.0
    return pd.DataFrame(
        {
            "precip_mm": rain,
            "precip_imerg_mm": rain,
            "precip_source": "IMERG_FINAL_V07",
            "tmax_c": 30.0,
            "tmin_c": 20.0,
        },
        index=days,
    )


@pytest.fixture
def data_with_series(data_dir: Path) -> Path:
    target = data_dir / "curated" / "camotan_jocotan"
    target.mkdir(parents=True)
    synthetic_daily().to_parquet(target / "daily.parquet")
    return data_dir


def make_client(
    app_engine: Engine, test_db: Any, data_dir: Path, **over: Any
) -> Iterator[TestClient]:
    settings = make_settings(
        test_db, data_dir, planting_rules_path=over.pop("rules", RULES), **over
    )
    app = create_app(
        settings,
        engine=app_engine,
        ports=default_ports(),
        dispatcher=NullDispatcher(),
        recover_on_start=False,
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def client(
    app_engine: Engine, test_db: Any, data_with_series: Path, tmp_path: Path
) -> Iterator[TestClient]:
    yield from make_client(
        app_engine, test_db, data_with_series, station_csv_path=tmp_path / "no_hay_estacion.csv"
    )


def headers(client: TestClient, world: World) -> dict[str, str]:
    r = client.post(
        "/v1/auth/login",
        json={"email": world.farmer_a_user["email"], "password": world.farmer_a_user["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_options_come_from_the_rules_json(client: TestClient, world: World, agro_zone: str) -> None:
    r = client.get(f"/v1/zones/{agro_zone}/planting-options", headers=headers(client, world))
    assert r.status_code == 200, r.text
    body = r.json()
    assert {c["clave"] for c in body["cultivos"]} == {"maiz", "frijol"}
    maize = next(c for c in body["cultivos"] if c["clave"] == "maiz")
    assert [v["nombre"] for v in maize["variedades"]] == [
        "ICTA B-7",
        "ICTA B-5",
        "ICTA B-9",
        "ICTA B-15",
    ]
    assert {c["ciclo"] for c in body["ciclos"]} == {"primera", "postrera"}
    assert "provisional" in body["aviso"].lower()


def test_validation_returns_kc_phenology_sources_and_uses_declared_water_signals(
    client: TestClient, world: World, agro_zone: str
) -> None:
    h = headers(client, world)
    url = f"/v1/zones/{agro_zone}/planting-validation"
    ok = client.get(
        url,
        params={
            "fecha_siembra": "2024-05-15",
            "variedad": "ICTA B-7",
            "ciclo": "primera",
            "dias_secos_recientes": 2,
            "lluvia_15_dias_mm": 60,
            "idioma": "en",
        },
        headers=h,
    ).json()
    assert (
        ok["es_valido"] is True
        and ok["kc_etapa_media"] == 1.2
        and ok["parametros_fenologicos"]["ciclo_total_dias"] == 120
    )
    assert ok["origen_senales_hidricas"] == "data declared by the user" and ok["fuentes"]
    bad = client.get(
        url,
        params={
            "fecha_siembra": "2024-07-20",
            "variedad": "ICTA B-7",
            "dias_secos_recientes": 12,
            "idioma": "en",
        },
        headers=h,
    ).json()
    assert (
        bad["es_valido"] is False
        and bad["fecha_en_ventana"] is False
        and bad["senal_sequia"] is True
    )
    assert any("not a prohibition" in a for a in bad["alertas"])
    zonal = client.get(
        url, params={"fecha_siembra": "2024-05-12", "variedad": "ICTA B-5"}, headers=h
    ).json()
    assert (
        zonal["precipitacion_15_dias_mm"] == pytest.approx(6 * 14 + 1 * 1, abs=0.01)
        or zonal["precipitacion_15_dias_mm"] > 60
    )
    assert zonal["origen_senales_hidricas"].startswith("serie histórica")


def test_unknown_variety_and_unknown_crop_are_reported_not_crashed(
    client: TestClient, world: World, agro_zone: str
) -> None:
    h = headers(client, world)
    url = f"/v1/zones/{agro_zone}/planting-validation"
    assert (
        client.get(
            url, params={"fecha_siembra": "2024-05-15", "variedad": "ICTA Falsa"}, headers=h
        ).json()["es_valido"]
        is False
    )
    r = client.get(
        url, params={"fecha_siembra": "2024-05-15", "variedad": "X", "cultivo": "quinua"}, headers=h
    )
    assert r.status_code == 200 and "no configurado" in r.json()["alertas"][0]
    assert (
        client.get(
            url,
            params={
                "fecha_siembra": "2024-05-15",
                "variedad": "ICTA B-7",
                "dias_secos_recientes": -1,
            },
            headers=h,
        ).status_code
        == 422
    )


def test_onset_estimation_detects_the_pentad_and_compares_with_sowing(
    client: TestClient, world: World, agro_zone: str
) -> None:
    h = headers(client, world)
    r = client.get(
        f"/v1/zones/{agro_zone}/rainy-season-onset",
        params={"anio": 2024, "fecha_siembra": "2024-05-20", "idioma": "en"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resultado"] == "detectado" and body["fecha_estimada_inicio"] == "2024-05-11"
    assert (
        body["es_metodo_oficial_insivumeh"] is False
        and "INSIVUMEH" in body["aviso"]
        and "Sandbox" in body["estado"]
    )
    assert (
        body["retraso_adaptacion"]["dias_diferencia"] == 9
        and body["retraso_adaptacion"]["conclusion"] == "dentro_del_rango"
    )
    assert len(body["precipitacion_pentadas"]) == 73
    assert (
        client.get(
            f"/v1/zones/{agro_zone}/rainy-season-onset", params={"anio": 2024}, headers=h
        ).json()["retraso_adaptacion"]
        is None
    )


def test_station_validation_defaults_to_level_c_and_never_offers_upload(
    client: TestClient, world: World, agro_zone: str
) -> None:
    body = client.get(
        f"/v1/zones/{agro_zone}/station-validation",
        params={"idioma": "en"},
        headers=headers(client, world),
    ).json()
    assert body["estado_validacion"] == "Nivel C - Pendiente" and body["metricas"] is None
    assert (
        body["carga_habilitada"] is False
        and body["fuente_sugerida"] == "INSIVUMEH - Estación Camotán"
    )
    assert (
        "No Camotán station data" in body["mensaje"]
        and "Historical station data are pending" in body["aviso"]
    )


def test_station_validation_reaches_level_b_only_with_a_real_long_csv(
    app_engine: Engine,
    test_db: Any,
    data_with_series: Path,
    tmp_path: Path,
    world: World,
    agro_zone: str,
) -> None:
    # estación PRUEBA = la serie sintética con algo de ruido, 366 días coincidentes
    sat = synthetic_daily()["precip_imerg_mm"]
    station = (sat + np.random.default_rng(3).normal(0, 0.4, len(sat))).clip(lower=0).round(2)
    real = tmp_path / "camotan_insivumeh.csv"
    real.write_text(
        "fecha,precipitacion_mm\n"
        + "\n".join(f"{d.date()},{v}" for d, v in station.items())
        + "\n",
        encoding="utf-8",
    )
    for csv, expected in (
        (real, "Nivel B - Validado localmente"),
        (EXAMPLE, "Nivel C - Pendiente"),
    ):
        gen = make_client(app_engine, test_db, data_with_series, station_csv_path=csv)
        c = next(gen)
        try:
            body = c.get(
                f"/v1/zones/{agro_zone}/station-validation", headers=headers(c, world)
            ).json()
            assert body["estado_validacion"] == expected, body
            if expected.startswith("Nivel B"):
                assert (
                    body["metricas"]["n_comparados"] == 366
                    and body["metricas"]["correlacion_pearson"] > 0.5
                )
            else:
                assert body["es_ejemplo_ficticio"] is True and body["metricas"] is None
        finally:
            gen.close()


def test_missing_or_broken_rules_only_disable_their_endpoints(
    app_engine: Engine,
    test_db: Any,
    data_with_series: Path,
    tmp_path: Path,
    world: World,
    agro_zone: str,
) -> None:
    broken = tmp_path / "mal.json"
    broken.write_text("{no es json", encoding="utf-8")
    for rules in (tmp_path / "ausente.json", broken):
        gen = make_client(app_engine, test_db, data_with_series, rules=rules)
        c = next(gen)
        try:
            h = headers(c, world)
            assert c.get("/healthz").status_code == 200
            r = c.get(f"/v1/zones/{agro_zone}/planting-options", headers=h)
            assert r.status_code == 503 and "no está disponible" in r.json()["detail"]
            assert c.get(f"/v1/zones/{agro_zone}/rainy-season-onset", headers=h).status_code == 503
            assert c.get(f"/v1/zones/{agro_zone}/station-validation", headers=h).status_code == 503
            assert (
                c.get("/v1/zones", headers=h).status_code == 200
            )  # el resto de la API sigue funcionando
        finally:
            gen.close()


def test_changing_the_window_in_the_json_changes_the_result_without_code_changes(
    app_engine: Engine,
    test_db: Any,
    data_with_series: Path,
    tmp_path: Path,
    world: World,
    agro_zone: str,
) -> None:
    data = json.loads(RULES.read_text(encoding="utf-8"))
    data["ventanas_siembra"]["primera"]["fin"] = "07-31"
    custom = tmp_path / "reglas.json"
    custom.write_text(json.dumps(data), encoding="utf-8")
    shutil.copy(RULES, tmp_path / "original.json")
    gen = make_client(app_engine, test_db, data_with_series, rules=custom)
    c = next(gen)
    try:
        r = c.get(
            f"/v1/zones/{agro_zone}/planting-validation",
            params={
                "fecha_siembra": "2024-07-20",
                "variedad": "ICTA B-7",
                "ciclo": "primera",
                "dias_secos_recientes": 0,
                "lluvia_15_dias_mm": 80,
            },
            headers=headers(c, world),
        )
        assert r.json()["fecha_en_ventana"] is True
    finally:
        gen.close()
