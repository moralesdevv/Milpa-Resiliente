"""Servicio de informes con PostgreSQL real (BE-07). El PDF (ReportLab) no requiere Pango ni Docker."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.adapters.not_integrated import default_ports
from api.config import Settings
from api.db.uow import unit_of_work
from api.jobs.dispatch import NullDispatcher
from api.main import create_app
from api.models.enums import UserRole
from api.reports.renderer import PublicReportPrivacyError
from api.reports.service import ReportService
from api.services.context import CurrentUser, ServiceContext
from api.storage.object_store import LocalObjectStore
from testkit.app import World
from testkit.reports import make, text_of


def service_ctx(engine: Engine, settings: Settings, data_dir: Path, user: dict[str, Any]) -> Any:
    cm = unit_of_work(engine, user["user_id"])
    uow = cm.__enter__()
    ctx = ServiceContext(
        uow=uow,
        user=CurrentUser(user["user_id"], UserRole(user["role"]), user["email"]),
        settings=settings,
        ports=default_ports(),
        store=LocalObjectStore(data_dir),
        dispatcher=NullDispatcher(),
    )
    return cm, ctx


def test_generate_registers_hash_and_serves_verified_pdf(
    app_engine: Engine, settings: Settings, data_dir: Path, world: World, admin_engine: Engine
) -> None:
    cm, ctx = service_ctx(app_engine, settings, data_dir, world.tech)
    try:
        report = ReportService(ctx).generate(make(run_id=None))
        rid, sha, uri = report.report_id, report.pdf_sha256, report.pdf_uri
    finally:
        cm.__exit__(None, None, None)
    pdf_bytes = (data_dir / str(uri)).read_bytes()
    assert pdf_bytes.startswith(b"%PDF") and hashlib.sha256(pdf_bytes).hexdigest() == sha
    with admin_engine.connect() as c:
        row = c.execute(
            text(
                "SELECT pdf_sha256, template_version, privacy_level, locale, content_json::text "
                "FROM report.report WHERE report_id=:r"
            ),
            {"r": rid},
        ).one()
    assert row.pdf_sha256 == sha and row.template_version == "provisional-technical-v0"
    assert row.privacy_level == "public" and "persona" not in row.content_json
    # descarga vía API: mismo hash; verificación de integridad; acceso por pertenencia
    app = create_app(
        settings, engine=app_engine, dispatcher=NullDispatcher(), recover_on_start=False
    )
    with TestClient(app) as c:
        tok = c.post(
            "/v1/auth/login",
            json={"email": world.tech["email"], "password": world.tech["password"]},
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        r = c.get(f"/v1/reports/{rid}/pdf", headers=h)
        assert (
            r.status_code == 200 and r.headers["X-Content-SHA256"] == sha and r.content == pdf_bytes
        )
        assert "Anexo técnico" in text_of(r.content)
        other = c.post(
            "/v1/auth/login",
            json={
                "email": world.farmer_b_user["email"],
                "password": world.farmer_b_user["password"],
            },
        )
        assert (
            c.get(
                f"/v1/reports/{rid}/pdf",
                headers={"Authorization": f"Bearer {other.json()['access_token']}"},
            ).status_code
            == 404
        )
        (data_dir / str(uri)).write_bytes(pdf_bytes + b"\n%alterado")
        bad = c.get(f"/v1/reports/{rid}/pdf", headers=h)
        assert bad.status_code == 500 and bad.json()["code"] == "INTEGRITY_CHECK_FAILED"


def test_generation_is_deterministic_for_same_input(
    app_engine: Engine, settings: Settings, data_dir: Path, world: World
) -> None:
    cm, ctx = service_ctx(app_engine, settings, data_dir, world.tech)
    try:
        a = ReportService(ctx).generate(make(run_id=None)).pdf_sha256
        b = ReportService(ctx).generate(make(run_id=None)).pdf_sha256
    finally:
        cm.__exit__(None, None, None)
    assert a == b  # mismo código + entrada + parámetros => mismo hash (misma imagen)


def test_public_report_with_sensitive_text_is_rejected_and_leaves_no_file(
    app_engine: Engine, settings: Settings, data_dir: Path, world: World, admin_engine: Engine
) -> None:
    cm, ctx = service_ctx(app_engine, settings, data_dir, world.tech)
    try:
        with pytest.raises(PublicReportPrivacyError):
            ReportService(ctx).generate(
                make(run_id=None, summary_es="escribir a persona@correo.example.org")
            )
    finally:
        cm.__exit__(None, None, None)
    assert (
        not list((data_dir / "reports").glob("*.pdf")) if (data_dir / "reports").exists() else True
    )
    with admin_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM report.report")).scalar_one() == 0


def test_internal_report_contains_names_but_public_does_not(
    app_engine: Engine, settings: Settings, data_dir: Path, world: World
) -> None:
    cm, ctx = service_ctx(app_engine, settings, data_dir, world.tech)
    try:
        svc = ReportService(ctx)
        internal = svc.generate(
            make(
                run_id=None,
                privacy_level="internal",
                internal={"farmer_display_name": "Nombre Privado", "parcel_code": "COD-9"},
            )
        )
        public = svc.generate(make(run_id=None))
        i_uri, p_uri = internal.pdf_uri, public.pdf_uri
    finally:
        cm.__exit__(None, None, None)
    assert "Nombre Privado" in text_of((data_dir / str(i_uri)).read_bytes())
    pub_text = text_of((data_dir / str(p_uri)).read_bytes())
    assert "Nombre Privado" not in pub_text and "COD-9" not in pub_text
