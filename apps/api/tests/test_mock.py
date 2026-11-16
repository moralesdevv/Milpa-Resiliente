"""El servidor mock devuelve solo ejemplos documentados y etiquetados; nunca simula ciencia."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from api.mock.app import build_mock, example_for, load_spec

SPEC = load_spec(Path(__file__).resolve().parents[3] / "docs" / "openapi" / "openapi.json")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(build_mock(SPEC))


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-4000-8000-000000000000", path)


def test_every_response_is_labelled_as_mock(client: TestClient) -> None:
    for path, ops in SPEC["paths"].items():
        for method in ops:
            r = client.request(method.upper(), concrete(path))
            assert r.headers["X-Milpa-Mock"] == "fixture", (method, path)
            assert r.status_code in {200, 201, 202, 501}, (method, path, r.status_code)


@pytest.mark.parametrize(
    "path",
    [
        "/v1/runs/{id}/summary",
        "/v1/runs/{id}/heatmap",
        "/v1/runs/{id}/dekad-chart",
        "/v1/runs/{id}/climate-history",
    ],
)
def test_r2_owned_endpoints_are_501_and_never_fabricate_science(
    client: TestClient, path: str
) -> None:
    r = client.get(concrete(path.replace("{id}", "x")))
    assert (
        r.status_code == 501
        and r.json()["code"] == "MOCK_NO_EXAMPLE"
        and "R2" in r.json()["detail"]
    )


def test_rank_and_voi_are_501(client: TestClient) -> None:
    for p in ("rank", "soil-voi"):
        r = client.post(concrete(f"/v1/runs/x/{p}"), json={})
        assert r.status_code == 501 and "R2" in r.json()["detail"]


def test_documented_examples_are_served_with_mock_marker(client: TestClient) -> None:
    health = client.get("/healthz").json()
    assert health["_mock"] == "fixture" and health["status"] == "ok"
    job = client.get(concrete("/v1/jobs/{id}")).json()
    assert job["kind"] == "report" and job["_mock"] == "fixture"
    page = client.get("/v1/zones").json()
    assert page["items"][0]["name"].endswith("(mock)") and page["next_cursor"] is None


def test_pdf_download_is_not_faked(client: TestClient) -> None:
    r = client.get(concrete("/v1/reports/{id}/pdf"))
    assert r.status_code == 501 and not r.content.startswith(b"%PDF")


def test_example_for_pending_contract_returns_reason() -> None:
    node: dict[str, Any] = {"x-contract-status": "pending_r2", "x-contract-owner": "R2"}
    ex, why = example_for({}, node)
    assert ex is None and "R2" in why
    assert json.dumps(SPEC)  # el documento es serializable
