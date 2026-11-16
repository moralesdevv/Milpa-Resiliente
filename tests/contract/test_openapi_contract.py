"""Contrato OpenAPI (BE-02): rutas de la especificación, seguridad, errores, marcas de contrato."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from api.jobs.dispatch import NullDispatcher
from api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "docs" / "openapi" / "openapi.json"

# Tabla de endpoints de la especificación R3 §10.2 (método, ruta). Cualquier cambio exige ADR.
SPEC_ENDPOINTS = {
    ("post", "/v1/auth/login"),
    ("get", "/v1/auth/me"),
    ("get", "/v1/zones"),
    ("get", "/v1/zones/{id}"),
    ("post", "/v1/zones"),
    ("get", "/v1/zones/{id}/data-quality"),
    ("post", "/v1/parcels"),
    ("get", "/v1/parcels/{id}"),
    ("delete", "/v1/parcels/{id}"),
    ("get", "/v1/parcels/{id}/soil"),
    ("post", "/v1/parcels/{id}/soil-samples"),
    ("put", "/v1/parcels/{id}/soil-declarations/{property}"),
    ("put", "/v1/parcels/{id}/priority-profile"),
    ("get", "/v1/catalog/crops"),
    ("get", "/v1/catalog/strategies"),
    ("get", "/v1/catalog/strategies/{id}/versions/{v}"),
    ("get", "/v1/catalog/references"),
    ("post", "/v1/zones/{id}/runs"),
    ("get", "/v1/runs/{id}"),
    ("get", "/v1/runs/{id}/scenarios"),
    ("post", "/v1/runs/{id}/scenarios"),
    ("get", "/v1/runs/{id}/climate-history"),
    ("get", "/v1/runs/{id}/summary"),
    ("get", "/v1/runs/{id}/heatmap"),
    ("get", "/v1/runs/{id}/dekad-chart"),
    ("post", "/v1/runs/{id}/rank"),
    ("post", "/v1/runs/{id}/soil-voi"),
    ("get", "/v1/provenance/{ip_id}"),
    ("post", "/v1/reports"),
    ("get", "/v1/reports/{id}"),
    ("get", "/v1/reports/{id}/pdf"),
    ("get", "/v1/jobs/{id}"),
    ("delete", "/v1/jobs/{id}"),
    ("get", "/healthz"),
}
PUBLIC = {("post", "/v1/auth/login"), ("get", "/healthz")}
ASYNC_202 = {
    ("post", "/v1/zones"),
    ("delete", "/v1/parcels/{id}"),
    ("post", "/v1/zones/{id}/runs"),
    ("post", "/v1/runs/{id}/scenarios"),
    ("post", "/v1/reports"),
}
PENDING_R2_SCHEMAS = {
    "PageStrategyRiskDTO",
    "ClimateHistoryDTO",
    "HeatmapDTO",
    "DekadChartDTO",
    "RankResponse",
    "SoilVoiResponse",
}


def build_schema() -> dict[str, Any]:
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:y@localhost/none")
    os.environ.setdefault("JWT_SECRET", "contract-test-jwt-secret-0123456789abcdef")
    app = create_app(dispatcher=NullDispatcher(), recover_on_start=False)
    schema: dict[str, Any] = app.openapi()
    return schema


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return build_schema()


def operations(schema: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(m, p): op for p, ops in schema["paths"].items() for m, op in ops.items()}


def test_openapi_is_3x_and_exposes_exactly_the_specified_endpoints(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["x-contract-status"] == "openapi_v0_draft"
    assert set(operations(schema)) == SPEC_ENDPOINTS


def test_all_versioned_routes_live_under_v1(schema: dict[str, Any]) -> None:
    assert all(p.startswith("/v1/") or p == "/healthz" for p in schema["paths"])


def test_protected_operations_declare_bearer_and_public_ones_do_not(schema: dict[str, Any]) -> None:
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    for key, op in operations(schema).items():
        if key in PUBLIC:
            assert "security" not in op, key
        else:
            assert op.get("security") == [{"HTTPBearer": []}], key


def test_error_responses_use_problem_detail_schema(schema: dict[str, Any]) -> None:
    for key, op in operations(schema).items():
        if key in PUBLIC and key[1] == "/healthz":
            continue
        responses = op["responses"]
        expected = {"401"} if key not in PUBLIC else set()
        assert expected <= set(responses), key
        for code, resp in responses.items():
            if code.startswith(("4", "5")) and "content" in resp:
                ref = next(iter(resp["content"].values()))["schema"]["$ref"]
                assert ref.endswith("/ProblemDetail"), (key, code)


def test_problem_detail_has_required_fields(schema: dict[str, Any]) -> None:
    pd = schema["components"]["schemas"]["ProblemDetail"]
    assert {"type", "title", "status", "code", "detail", "request_id"} <= set(pd["required"])
    assert "errors" in pd["properties"] and "hint" in pd["properties"]


def test_async_operations_declare_202(schema: dict[str, Any]) -> None:
    ops = operations(schema)
    for key in ASYNC_202:
        assert "202" in ops[key]["responses"], key
        assert ops[key]["responses"]["202"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/JobOut")


def test_idempotency_key_header_on_job_creating_operations(schema: dict[str, Any]) -> None:
    for key in ASYNC_202:
        names = {p["name"] for p in operations(schema)[key].get("parameters", [])}
        assert "Idempotency-Key" in names, key


def test_r2_owned_responses_are_marked_pending_not_definitive(schema: dict[str, Any]) -> None:
    comps = schema["components"]["schemas"]
    for name in PENDING_R2_SCHEMAS:
        assert comps[name]["x-contract-status"] == "pending_r2", name
        assert comps[name]["x-contract-owner"] == "R2"


def test_unconfirmed_contracts_are_flagged_provisional(schema: dict[str, Any]) -> None:
    comps = schema["components"]["schemas"]
    for name in [
        "ParcelCreate",
        "ZoneCreate",
        "RunCreate",
        "ReportCreate",
        "RankRequest",
        "SoilCsvResult",
        "JobOut",
        "TokenResponse",
        "ParcelOut",
        "PriorityProfileIn",
    ]:
        assert comps[name].get("x-contract-status") == "provisional_r3", name


def test_csv_endpoint_declares_text_csv_body_and_size_errors(schema: dict[str, Any]) -> None:
    op = operations(schema)[("post", "/v1/parcels/{id}/soil-samples")]
    assert "text/csv" in op["requestBody"]["content"]
    assert {"413", "415", "422", "503"} <= set(op["responses"])


def test_privacy_no_exact_geometry_field_in_any_schema(schema: dict[str, Any]) -> None:
    names = json.dumps(schema).lower()
    for forbidden in ("exact_geom", "exact_geometry_wkt", "parcel_geometry"):
        assert forbidden not in names


def test_operation_ids_unique_and_refs_resolve(schema: dict[str, Any]) -> None:
    ids = [op["operationId"] for op in operations(schema).values()]
    assert len(ids) == len(set(ids))
    refs: set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "$ref":
                    refs.add(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(schema)
    for ref in refs:
        node: Any = schema
        for part in ref.removeprefix("#/").split("/"):
            node = node[part]


def test_schemathesis_accepts_the_document_as_valid_openapi(schema: dict[str, Any]) -> None:
    import schemathesis

    loaded = schemathesis.openapi.from_dict(schema)
    assert len(list(loaded.get_all_operations())) == len(SPEC_ENDPOINTS)


def test_committed_openapi_snapshot_matches_generated(schema: dict[str, Any]) -> None:
    """El OpenAPI versionado debe regenerarse con `make openapi` ante cualquier cambio de contrato."""
    if not SNAPSHOT.is_file():
        pytest.fail("Falta docs/openapi/openapi.json: ejecute `make openapi`")
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(schema, sort_keys=True)), (
        "OpenAPI desactualizado: make openapi"
    )
