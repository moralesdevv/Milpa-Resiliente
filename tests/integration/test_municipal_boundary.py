"""Límite municipal de Jocotán en el servidor (ADR-022): la ubicación de una parcela se valida con PostGIS.

La interfaz solo ayuda; lo que cuenta es esta validación. Se usa el GeoJSON REAL del repositorio y una
zona rectangular (la de ``regions/chiquimula_prueba.geojson``) que abarca Jocotán, Camotán y Chiquimula, de
modo que hay puntos dentro de la zona pero fuera del municipio.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.adapters.not_integrated import default_ports
from api.config import Settings
from api.geo.boundary import BoundaryError, load_boundary, parse_boundary
from api.jobs.dispatch import NullDispatcher
from api.main import create_app
from testkit import ROOT
from testkit.app import World, make_settings

BOUNDARY = ROOT / "regions" / "jocotan_chiquimula_boundary.geojson"
ZONE_WKT = "POLYGON((-89.60 14.75, -89.20 14.75, -89.20 14.95, -89.60 14.95, -89.60 14.75))"

JOCOTAN_TOWN = (
    14.8194,
    -89.3903,
)  # punto público de referencia (nota de regions/camotan_jocotan.geojson)
CAMOTAN_TOWN = (14.8203, -89.3733)  # municipio vecino: dentro de la zona, FUERA de Jocotán
BBOX_CORNER = (14.90, -89.22)  # dentro de la caja envolvente de Jocotán pero fuera de su polígono


@pytest.fixture
def jocotan_zone(admin_engine: Engine) -> str:
    with admin_engine.begin() as c:
        region = c.execute(
            text(
                "INSERT INTO geo.region (code, name, config_uri, config_hash, bbox) VALUES "
                "('JOC', 'Región Jocotán', 'test://jocotan', repeat('0',64), ST_GeomFromText(:g,4326)) "
                "RETURNING region_id"
            ),
            {"g": ZONE_WKT},
        ).scalar_one()
        zone = c.execute(
            text(
                "INSERT INTO geo.zone (region_id, name, geom) VALUES (:r, 'zona_jocotan_prueba', "
                "ST_Multi(ST_GeomFromText(:g,4326))) RETURNING zone_id"
            ),
            {"r": region, "g": ZONE_WKT},
        ).scalar_one()
    return str(zone)


@pytest.fixture
def boundary_client(app_engine: Engine, test_db: Any, data_dir: Path) -> Iterator[TestClient]:
    settings: Settings = make_settings(test_db, data_dir, municipal_boundary_file=BOUNDARY)
    app = create_app(
        settings,
        engine=app_engine,
        ports=default_ports(),
        dispatcher=NullDispatcher(),
        recover_on_start=False,
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def post_parcel(
    client: TestClient,
    headers: dict[str, str],
    zone: str,
    point: tuple[float, float],
    **over: Any,
) -> Any:
    payload = {"zone_id": zone, "location": {"lat": point[0], "lon": point[1]}, "code": "P-JOC"}
    payload.update(over)
    return client.post("/v1/parcels", json=payload, headers=headers)


def farmer_headers(client: TestClient, world: World) -> dict[str, str]:
    r = client.post(
        "/v1/auth/login",
        json={"email": world.farmer_a_user["email"], "password": world.farmer_a_user["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------------------- archivo de límite
def test_real_boundary_file_is_valid_and_documented() -> None:
    boundary = load_boundary(BOUNDARY)
    assert boundary.name == "Jocotán" and boundary.department == "Chiquimula"
    assert (boundary.municipal_code, boundary.department_code) == (2004, 20)
    assert boundary.n_vertices > 100 and len(boundary.sha256) == 64
    lon_min, lat_min, lon_max, lat_max = boundary.bbox
    assert -89.6 < lon_min < lon_max < -89.1 and 14.6 < lat_min < lat_max < 15.0


def test_postgis_agrees_the_boundary_polygon_is_valid_and_has_municipal_size(
    admin_engine: Engine,
) -> None:
    geometry = load_boundary(BOUNDARY).geometry_json
    with admin_engine.connect() as c:
        valid, reason, area_km2 = c.execute(
            text(
                "WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326) AS geom) "
                "SELECT ST_IsValid(geom), ST_IsValidReason(geom), ST_Area(geom::geography) / 1e6 FROM g"
            ),
            {"g": geometry},
        ).one()
    assert valid, reason
    assert 200 < area_km2 < 300  # un municipio del orden de 250 km², no un rectángulo de prueba


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(type="Feature"), "FeatureCollection"),
        (lambda d: d["features"].append(d["features"][0]), "exactamente un Feature"),
        (
            lambda d: d.update(crs={"type": "name", "properties": {"name": "EPSG:32616"}}),
            "CRS no admitido",
        ),
        (
            lambda d: d["features"][0]["geometry"]["coordinates"][0].__setitem__(0, [0.0, 0.0]),
            "fuera de Guatemala",
        ),
        (
            lambda d: d["features"][0]["geometry"]["coordinates"][0].pop(),
            "no está cerrado",
        ),
        (lambda d: d["features"][0].update(properties={}), "nombre del municipio"),
        (lambda d: d["features"][0]["geometry"].update(type="Point"), "Polygon"),
    ],
)
def test_malformed_boundaries_are_rejected_with_a_reason(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    data = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    mutate(data)
    with pytest.raises(BoundaryError, match=message):
        parse_boundary(json.dumps(data).encode())


def test_self_intersecting_ring_is_rejected() -> None:
    bow_tie = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NOMBRE_1": "X", "DEPTO_1": "Y"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-89.5, 14.7], [-89.2, 14.9], [-89.2, 14.7], [-89.5, 14.9], [-89.5, 14.7]]
                    ],
                },
            }
        ],
    }
    with pytest.raises(BoundaryError, match="se cruza a sí mismo"):
        parse_boundary(json.dumps(bow_tie).encode())


# ------------------------------------------------------------------------------- validación en servidor
def test_parcel_inside_jocotan_is_accepted_and_only_the_generalized_cell_is_stored(
    boundary_client: TestClient, world: World, jocotan_zone: str, admin_engine: Engine
) -> None:
    headers = farmer_headers(boundary_client, world)
    r = post_parcel(boundary_client, headers, jocotan_zone, JOCOTAN_TOWN)
    assert r.status_code == 201, r.text
    data = r.json()
    assert round(data["display_location"]["lat"], 3) == data["display_location"]["lat"]
    assert data["display_grid_m"] == 1000
    assert (
        "14.8194" not in r.text and "89.3903" not in r.text
    )  # el punto exacto no vuelve en la respuesta
    with admin_engine.connect() as c:
        dump = c.execute(
            text("SELECT p::text FROM farm.parcel p WHERE parcel_id=:i"), {"i": data["parcel_id"]}
        ).scalar_one()
    assert "14.8194" not in dump and "89.3903" not in dump


@pytest.mark.parametrize(
    "point", [CAMOTAN_TOWN, BBOX_CORNER], ids=["municipio-vecino", "esquina-bbox"]
)
def test_point_inside_the_zone_but_outside_jocotan_is_rejected_by_the_server(
    boundary_client: TestClient,
    world: World,
    jocotan_zone: str,
    admin_engine: Engine,
    point: tuple[float, float],
) -> None:
    headers = farmer_headers(boundary_client, world)
    r = post_parcel(boundary_client, headers, jocotan_zone, point)
    assert r.status_code == 422, r.text
    assert "fuera de Jocotán, Chiquimula" in r.json()["detail"]
    assert str(point[0]) not in r.text and str(point[1]) not in r.text  # no se repite la coordenada
    with admin_engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM farm.parcel WHERE zone_id = :z"), {"z": jocotan_zone}
            ).scalar_one()
            == 0
        )


def test_point_outside_the_zone_is_still_rejected_first(
    boundary_client: TestClient, world: World, jocotan_zone: str
) -> None:
    headers = farmer_headers(boundary_client, world)
    r = post_parcel(boundary_client, headers, jocotan_zone, (14.5, -89.5))
    assert r.status_code == 422 and "no está dentro de la zona" in r.json()["detail"]


def test_without_a_configured_boundary_only_the_zone_rule_applies(
    client: TestClient, login: Any, world: World, jocotan_zone: str
) -> None:
    r = post_parcel(client, login(world.farmer_a_user), jocotan_zone, CAMOTAN_TOWN)
    assert r.status_code == 201, r.text  # comportamiento anterior: la zona manda


def test_unusable_boundary_file_fails_closed_without_leaking_the_point(
    app_engine: Engine, test_db: Any, data_dir: Path, world: World, jocotan_zone: str
) -> None:
    broken = data_dir / "broken.geojson"
    broken.write_text("{ no es json", encoding="utf-8")
    settings = make_settings(test_db, data_dir, municipal_boundary_file=broken)
    app = create_app(
        settings,
        engine=app_engine,
        ports=default_ports(),
        dispatcher=NullDispatcher(),
        recover_on_start=False,
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        r = post_parcel(c, farmer_headers(c, world), jocotan_zone, JOCOTAN_TOWN)
    assert r.status_code == 503, r.text  # no se acepta una ubicación que no se pudo validar
    assert "14.8194" not in r.text and "89.3903" not in r.text


def test_other_farmer_cannot_read_the_parcel_created_inside_jocotan(
    boundary_client: TestClient, world: World, jocotan_zone: str
) -> None:
    created = post_parcel(
        boundary_client, farmer_headers(boundary_client, world), jocotan_zone, JOCOTAN_TOWN
    )
    assert created.status_code == 201
    other = boundary_client.post(
        "/v1/auth/login",
        json={"email": world.farmer_b_user["email"], "password": world.farmer_b_user["password"]},
    ).json()["access_token"]
    got = boundary_client.get(
        f"/v1/parcels/{created.json()['parcel_id']}", headers={"Authorization": f"Bearer {other}"}
    )
    assert got.status_code == 404  # RLS: no se distingue de «no existe»
