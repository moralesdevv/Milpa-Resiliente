"""Paridad de enums Python <-> SQL <-> OpenAPI (README §15 "Pruebas de contrato", spec R3 §11.3)."""

from __future__ import annotations

import re
from enum import StrEnum

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.contracts.provisional_enums import (
    ENUM_SOURCE,
    SQL_TYPE_TO_ENUM,
    AdaptationMode,
    PropertyStatus,
)
from api.models.enums import ConsentPurpose, JobKind, JobStatus, PrivacyLevel, UserRole


def sql_enum_values(engine: Engine, type_name: str) -> list[str]:
    with engine.connect() as c:
        return list(
            c.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid "
                    "WHERE t.typname=:n ORDER BY e.enumsortorder"
                ),
                {"n": type_name},
            ).scalars()
        )


def check_constraint_values(engine: Engine, table: str, column: str) -> set[str]:
    with engine.connect() as c:
        defs = (
            c.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=CAST(:t AS regclass) AND contype='c'"
                ),
                {"t": table},
            )
            .scalars()
            .all()
        )
    for d in defs:
        if re.search(rf"\b{column}\b", d) and "ARRAY" in d:
            return set(re.findall(r"'([^']+)'::text", d))
    raise AssertionError(f"sin CHECK de enumeración para {table}.{column}")


@pytest.mark.parametrize(
    "sql_type,py_enum", [(k, v) for k, v in SQL_TYPE_TO_ENUM.items() if v is not None]
)
def test_scientific_enums_python_equals_sql(
    admin_engine: Engine, sql_type: str, py_enum: type[StrEnum]
) -> None:
    assert sql_enum_values(admin_engine, sql_type) == [m.value for m in py_enum], sql_type


def test_known_contract_gap_window_mode_has_no_shared_enum(admin_engine: Engine) -> None:
    """window_mode_t existe en SQL pero README §15 no lo lista entre los enums compartidos."""
    assert SQL_TYPE_TO_ENUM["window_mode_t"] is None
    assert sql_enum_values(admin_engine, "window_mode_t") == [
        "candidate_dates",
        "fixed_season_window",
        "relative_to_previous_harvest",
    ]


def test_every_sql_enum_is_accounted_for(admin_engine: Engine) -> None:
    with admin_engine.connect() as c:
        in_db = set(c.execute(text("SELECT typname FROM pg_type WHERE typtype='e'")).scalars())
    r3_owned = {"user_role_t", "job_status_t"}
    assert (
        in_db == set(SQL_TYPE_TO_ENUM) | r3_owned
    )  # un enum nuevo en SQL sin contraparte rompe la prueba


def test_enum_source_is_declared_provisional_until_r2_delivers() -> None:
    assert ENUM_SOURCE == "provisional-readme-15"  # cambiar SOLO al sustituir por milpa_core.enums


def test_r3_owned_enums_python_equals_sql(admin_engine: Engine) -> None:
    assert sql_enum_values(admin_engine, "user_role_t") == [m.value for m in UserRole]
    assert sql_enum_values(admin_engine, "job_status_t") == [m.value for m in JobStatus]
    assert check_constraint_values(admin_engine, "engine.job", "kind") == {m.value for m in JobKind}
    assert check_constraint_values(admin_engine, "auth.consent", "purpose") == {
        m.value for m in ConsentPurpose
    }
    assert check_constraint_values(admin_engine, "report.report", "privacy_level") == {
        m.value for m in PrivacyLevel
    }


def test_stability_flag_has_the_four_algorithm_states(admin_engine: Engine) -> None:
    """README T-P16: los cuatro estados existen en SQL y en el DTO."""
    assert set(sql_enum_values(admin_engine, "stability_flag_t")) == {
        "stable",
        "moderate",
        "unstable",
        "insufficient",
    }


def openapi_enums(client: TestClient) -> dict[str, list[str]]:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    return {name: s["enum"] for name, s in schemas.items() if "enum" in s}


@pytest.mark.parametrize(
    "name,py_enum",
    [
        ("JobStatus", JobStatus),
        ("JobKind", JobKind),
        ("UserRole", UserRole),
        ("AdaptationMode", AdaptationMode),
        ("PropertyStatus", PropertyStatus),
    ],
)
def test_openapi_enums_equal_python(client: TestClient, name: str, py_enum: type[StrEnum]) -> None:
    enums = openapi_enums(client)
    assert name in enums, f"{name} no aparece en OpenAPI"
    assert enums[name] == [m.value for m in py_enum]


def test_openapi_enums_equal_sql_for_exposed_types(
    client: TestClient, admin_engine: Engine
) -> None:
    enums = openapi_enums(client)
    pairs = {
        "JobStatus": "job_status_t",
        "UserRole": "user_role_t",
        "AdaptationMode": "adaptation_t",
        "PropertyStatus": "property_status_t",
    }
    for api_name, sql_type in pairs.items():
        assert enums[api_name] == sql_enum_values(admin_engine, sql_type), api_name


def test_typescript_parity_requires_r4_generated_types() -> None:
    from pathlib import Path

    ts = Path(__file__).resolve().parents[2] / "docs" / "openapi" / "types.generated.d.ts"
    if not ts.is_file():
        pytest.skip(
            "Tipos TypeScript no generados: dependen del entorno de R4 (make types). Estado: pending"
        )
    text_ = ts.read_text(encoding="utf-8")
    for member in [m.value for m in JobStatus] + [m.value for m in UserRole]:
        assert f'"{member}"' in text_, member


# --- R2 (milpa_core) <-> SQL ---------------------------------------------------------------------
R2_TO_SQL_NAME = {"adaptation_mode_t": "adaptation_t", "humidity_assumption_t": "humidity_t"}


def test_milpa_core_enums_equal_the_database_enum_types(admin_engine: Engine) -> None:
    """Cada tipo ENUM de milpa_core que existe en la base tiene los mismos valores y el mismo orden."""
    milpa_enums = pytest.importorskip("milpa_core.enums")
    declared = re.findall(r"CREATE TYPE (\w+) AS ENUM \((.*?)\);", milpa_enums.export_sql())
    assert declared, "milpa_core no exportó tipos"
    compared = 0
    for name, body in declared:
        values = re.findall(r"'([^']*)'", body)
        sql_values = sql_enum_values(admin_engine, R2_TO_SQL_NAME.get(name, name))
        if (
            not sql_values
        ):  # tipo sin ENUM en la base (se guarda como texto con CHECK o no se persiste)
            continue
        assert sql_values == values, name
        compared += 1
    assert compared >= 14  # los tipos persistidos como ENUM de PostgreSQL
