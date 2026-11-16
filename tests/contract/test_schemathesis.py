"""T-C: Schemathesis contra el OpenAPI de la aplicación real (con PostgreSQL real).

Dos pasadas por operación: sin credenciales y con un token válido de técnico. Comprueba que
(1) ninguna entrada generada provoca un 5xx, (2) toda respuesta cumple su esquema documentado y
(3) el tipo de contenido coincide con el documentado.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from schemathesis import openapi
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
)

from testkit import PASSWORD
from testkit.app import World

CHECKS = [not_a_server_error, response_schema_conformance, content_type_conformance]
EXPECTED_OPERATIONS = 34


def run_operations(app: Any, headers: dict[str, str], max_examples: int) -> int:
    schema = openapi.from_asgi("/openapi.json", app)
    count = 0
    for result in schema.get_all_operations():
        operation = result.ok()

        @settings(
            max_examples=max_examples,
            deadline=None,
            database=None,
            suppress_health_check=list(HealthCheck),
        )
        @given(case=operation.as_strategy())
        def check(case: Any) -> None:
            case.call_and_validate(headers=headers, checks=CHECKS)

        check()
        count += 1
    return count


def test_schemathesis_unauthenticated_requests(client: TestClient) -> None:
    assert run_operations(client.app, {}, max_examples=8) == EXPECTED_OPERATIONS


def test_schemathesis_authenticated_requests(client: TestClient, world: World) -> None:
    tok = client.post(
        "/v1/auth/login", json={"email": world.tech["email"], "password": PASSWORD}
    ).json()["access_token"]
    n = run_operations(client.app, {"Authorization": f"Bearer {tok}"}, max_examples=8)
    assert n == EXPECTED_OPERATIONS
