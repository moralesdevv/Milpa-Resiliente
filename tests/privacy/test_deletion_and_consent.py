"""Borrado integral de parcela, consentimiento y su retirada (BE-03, R3-F05/F06, T-S)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.db.uow import unit_of_work
from api.errors import NotFound, ValidationFailed
from api.jobs.dispatch import InlineDispatcher, WorkerConfig
from api.jobs.worker import run_job
from api.models.enums import ConsentPurpose, JobKind, JobStatus
from api.services.consent import ConsentService
from testkit.app import World
from tests.integration.test_jobs import new_job, state  # type: ignore[import-not-found]


@pytest.fixture
def dispatcher(worker_config: WorkerConfig) -> InlineDispatcher:
    return InlineDispatcher(worker_config)


def populate(world: World, data_dir: Path) -> dict[str, Any]:
    """Una parcela con TODOS los tipos de dato dependiente + archivos en disco."""
    f = world.f
    f.soil_property("ph")
    ip = f.sample_with_measurement(world.parcel_a, "ph", 6.2)
    run = f.run(world.zone, world.parcel_a, created_by=world.farmer_a_user["user_id"])
    f.scenario(run, "BASE", "none")
    res_dir = data_dir / "results" / str(run) / "BASE" / "none"
    res_dir.mkdir(parents=True)
    (res_dir / "cycle_result.parquet").write_bytes(b"PAR1-fake")
    pdf_rel = f"reports/{UUID(int=1)}.pdf"
    (data_dir / "reports").mkdir(exist_ok=True)
    (data_dir / pdf_rel).write_bytes(b"%PDF-fake")
    report = f.report(world.farmer_a_user["user_id"], run, "public", pdf_rel)
    f._exec(
        "INSERT INTO farm.priority_profile (parcel_id, w_water, w_soil, w_food, w_income) VALUES (:p,.25,.25,.25,.25)",
        p=world.parcel_a,
    )
    f._exec(
        "INSERT INTO prov.indicator_provenance (run_id, indicator_code, unit, provenance, evidence_level, source_ids, processing_method, evidence_rule_id) "
        "VALUES (:r,'x','u','modelado','B','{}','m','r')",
        r=run,
    )
    return {"run": run, "ip": ip, "report": report, "res_dir": res_dir, "pdf": data_dir / pdf_rel}


def count(admin: Engine, sql: str, **p: Any) -> int:
    with admin.connect() as c:
        return int(c.execute(text(sql), p).scalar_one())


def test_parcel_delete_removes_rows_files_and_keeps_other_parcels(
    client: TestClient, login: Any, world: World, admin_engine: Engine, data_dir: Path
) -> None:
    other = populate_other(world)
    art = populate(world, data_dir)
    r = client.delete(f"/v1/parcels/{world.parcel_a}", headers=login(world.farmer_a_user))
    assert r.status_code == 202
    job = client.get(f"/v1/jobs/{r.json()['job_id']}", headers=login(world.farmer_a_user)).json()
    assert (
        job["status"] == "ok"
        and job["result"]["parcel_deleted"] is True
        and job["result"]["files_removed"] >= 2
    )

    pa = {"p": world.parcel_a}
    for table, col in [
        ("farm.parcel", "parcel_id"),
        ("soil.sample", "parcel_id"),
        ("soil.declaration", "parcel_id"),
        ("farm.priority_profile", "parcel_id"),
        ("engine.analysis_run", "parcel_id"),
    ]:
        assert count(admin_engine, f"SELECT count(*) FROM {table} WHERE {col}=:p", **pa) == 0, table
    assert count(admin_engine, "SELECT count(*) FROM soil.measurement") == other["measurements"]
    assert (
        count(
            admin_engine, "SELECT count(*) FROM report.report WHERE report_id=:r", r=art["report"]
        )
        == 0
    )
    assert (
        count(
            admin_engine, "SELECT count(*) FROM engine.scenario_run WHERE run_id=:r", r=art["run"]
        )
        == 0
    )
    assert (
        count(
            admin_engine,
            "SELECT count(*) FROM prov.indicator_provenance WHERE ip_id=:i OR run_id=:r",
            i=art["ip"],
            r=art["run"],
        )
        == 0
    )
    assert not art["res_dir"].exists() and not art["pdf"].exists()
    # la otra parcela y sus datos siguen intactos
    assert (
        count(admin_engine, "SELECT count(*) FROM farm.parcel WHERE parcel_id=:p", p=world.parcel_b)
        == 1
    )


def populate_other(world: World) -> dict[str, int]:
    world.f.soil_property("ph")
    world.f.sample_with_measurement(world.parcel_b, "ph", 5.5)
    return {"measurements": 1}


def test_delete_audit_trail_has_only_technical_ids_and_date(
    client: TestClient, login: Any, world: World, admin_engine: Engine, data_dir: Path
) -> None:
    populate(world, data_dir)
    client.delete(f"/v1/parcels/{world.parcel_a}", headers=login(world.farmer_a_user))
    with admin_engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT actor_user_id, action, resource_type, resource_id, details, at FROM auth.audit_log WHERE action='parcel.delete'"
            )
        ).all()
    assert len(rows) == 1 and rows[0].resource_id == world.parcel_a and rows[0].at is not None
    dump = json.dumps([str(x) for x in rows[0]])
    for personal in ("PARCELA-A", "Agricultora A", world.farmer_a_user["email"], "Comunidad"):
        assert personal not in dump


def test_delete_is_idempotent_and_resumes_file_cleanup_after_crash(
    app_engine: Engine,
    admin_engine: Engine,
    worker_config: WorkerConfig,
    world: World,
    data_dir: Path,
) -> None:
    """Simula caída entre 'filas borradas' y 'archivos borrados': el checkpoint completa el borrado."""
    art = populate(world, data_dir)
    jid = new_job(
        app_engine,
        JobKind.parcel_delete,
        {"v": 1, "parcel_id": str(world.parcel_a)},
        user=world.farmer_a_user["user_id"],
    )
    with (
        admin_engine.connect() as c
    ):  # estado tras la caída: checkpoint guardado, filas ya borradas
        c.execute(
            text("UPDATE engine.job SET result=CAST(:r AS jsonb) WHERE job_id=:j"),
            {
                "r": json.dumps(
                    {
                        "v": 1,
                        "stage": "db_pending",
                        "result_dirs": [f"results/{art['run']}"],
                        "pdfs": [str(art["pdf"].relative_to(data_dir)).replace("\\", "/")],
                    }
                ),
                "j": jid,
            },
        )
        c.execute(text("DELETE FROM report.report"))
        c.execute(text("DELETE FROM engine.scenario_run"))
        c.execute(text("DELETE FROM prov.indicator_provenance WHERE run_id IS NOT NULL"))
        c.execute(text("DELETE FROM engine.analysis_run"))
        c.execute(text("DELETE FROM soil.measurement"))
        c.execute(text("DELETE FROM soil.sample"))
        c.execute(text("DELETE FROM farm.priority_profile"))
        c.execute(text("DELETE FROM farm.parcel WHERE parcel_id=:p"), {"p": world.parcel_a})
    assert art["res_dir"].exists() and art["pdf"].exists()
    run_job(jid, worker_config)
    st = state(app_engine, jid)
    assert (
        st["status"] == JobStatus.ok
        and st["result"]["parcel_deleted"] is False
        and st["result"]["files_removed"] == 2
    )
    assert not art["res_dir"].exists() and not art["pdf"].exists()
    jid2 = new_job(
        app_engine,
        JobKind.parcel_delete,
        {"v": 1, "parcel_id": str(world.parcel_a)},
        user=world.farmer_a_user["user_id"],
    )
    run_job(jid2, worker_config)  # segunda ejecución: sin efectos ni errores
    assert state(app_engine, jid2)["status"] == JobStatus.ok


def test_user_cannot_delete_foreign_parcel_even_if_job_is_forged(
    app_engine: Engine, worker_config: WorkerConfig, world: World, admin_engine: Engine
) -> None:
    """Defensa en profundidad: aunque se cree un job a mano, RLS impide borrar la parcela ajena."""
    jid = new_job(
        app_engine,
        JobKind.parcel_delete,
        {"v": 1, "parcel_id": str(world.parcel_a)},
        user=world.farmer_b_user["user_id"],
    )
    run_job(jid, worker_config)
    assert state(app_engine, jid)["result"]["parcel_deleted"] is False
    assert (
        count(admin_engine, "SELECT count(*) FROM farm.parcel WHERE parcel_id=:p", p=world.parcel_a)
        == 1
    )


# ----------------------------------------------------------------------- consentimiento
def make_consent_service(
    app_engine: Engine, user_id: UUID, dispatcher: Any
) -> tuple[Any, ConsentService]:
    cm = unit_of_work(app_engine, user_id)
    uow = cm.__enter__()
    return cm, ConsentService(uow, dispatcher)


def test_withdrawing_analysis_consent_blocks_use_and_purges_results(
    app_engine: Engine,
    admin_engine: Engine,
    world: World,
    data_dir: Path,
    dispatcher: InlineDispatcher,
    client: TestClient,
    login: Any,
) -> None:
    art = populate(world, data_dir)
    uid = world.farmer_a_user["user_id"]
    cm, svc = make_consent_service(app_engine, uid, dispatcher)
    try:
        job_id = svc.withdraw(uid, ConsentPurpose.analysis)
    finally:
        cm.__exit__(None, None, None)
    st = state(app_engine, job_id)
    assert st["status"] == JobStatus.ok and st["result"]["purpose"] == "analysis"
    with admin_engine.connect() as c:
        w = c.execute(
            text("SELECT withdrawn_at FROM auth.consent WHERE consent_id=:c"),
            {"c": world.consent_a},
        ).scalar_one()
    assert w is not None
    # resultados y PDFs derivados desaparecen; la parcela y el suelo siguen hasta que se borre la parcela
    assert (
        count(
            admin_engine,
            "SELECT count(*) FROM engine.analysis_run WHERE parcel_id=:p",
            p=world.parcel_a,
        )
        == 0
    )
    assert not art["res_dir"].exists() and not art["pdf"].exists()
    assert (
        count(admin_engine, "SELECT count(*) FROM farm.parcel WHERE parcel_id=:p", p=world.parcel_a)
        == 1
    )
    # nuevos usos bloqueados y el técnico pierde acceso
    assert client.get(f"/v1/parcels/{world.parcel_a}", headers=login(world.tech)).status_code == 404
    prof = client.put(
        f"/v1/parcels/{world.parcel_a}/priority-profile",
        headers=login(world.farmer_a_user),
        json={"w_water": "0.25", "w_soil": "0.25", "w_food": "0.25", "w_income": "0.25"},
    )
    assert prof.json()["code"] == "CONSENT_REQUIRED"
    audit = count(
        admin_engine, "SELECT count(*) FROM auth.audit_log WHERE action='consent.withdraw'"
    )
    assert audit == 1


def test_withdrawing_report_sharing_deletes_public_reports_only(
    app_engine: Engine,
    admin_engine: Engine,
    world: World,
    data_dir: Path,
    dispatcher: InlineDispatcher,
) -> None:
    art = populate(world, data_dir)
    uid = world.farmer_a_user["user_id"]
    world.f.consent(world.farmer_a_user, "report_sharing")
    internal_pdf = "reports/internal.pdf"
    (data_dir / internal_pdf).write_bytes(b"%PDF-internal")
    internal = world.f.report(uid, art["run"], "internal", internal_pdf)
    cm, svc = make_consent_service(app_engine, uid, dispatcher)
    try:
        svc.withdraw(uid, ConsentPurpose.report_sharing)
    finally:
        cm.__exit__(None, None, None)
    assert (
        count(
            admin_engine, "SELECT count(*) FROM report.report WHERE report_id=:r", r=art["report"]
        )
        == 0
    )
    assert (
        count(admin_engine, "SELECT count(*) FROM report.report WHERE report_id=:r", r=internal)
        == 1
    )
    assert not art["pdf"].exists() and (data_dir / internal_pdf).exists()


def test_withdrawing_exact_geometry_consent_deletes_private_geometry(
    app_engine: Engine, admin_engine: Engine, world: World, dispatcher: InlineDispatcher
) -> None:
    uid = world.farmer_a_user["user_id"]
    gc = world.f.consent(world.farmer_a_user, "exact_geometry")
    with admin_engine.connect() as c:
        c.execute(
            text(
                "INSERT INTO private.parcel_geometry (parcel_id, exact_geom, consent_id) VALUES (:p, "
                "ST_GeomFromText('POLYGON((-89.5 14.5,-89.49 14.5,-89.49 14.51,-89.5 14.5))',4326), :c)"
            ),
            {"p": world.parcel_a, "c": gc},
        )
    cm, svc = make_consent_service(app_engine, uid, dispatcher)
    try:
        svc.withdraw(uid, ConsentPurpose.exact_geometry)
    finally:
        cm.__exit__(None, None, None)
    assert count(admin_engine, "SELECT count(*) FROM private.parcel_geometry") == 0


def test_consent_grant_is_idempotent_records_version_and_requires_text(
    app_engine: Engine, admin_engine: Engine, world: World
) -> None:
    uid = world.farmer_b_user["user_id"]
    with unit_of_work(app_engine, uid) as uow:
        svc = ConsentService(uow)
        first = svc.grant(uid, ConsentPurpose.report_sharing, "texto-v2")
        again = svc.grant(uid, ConsentPurpose.report_sharing, "texto-v3")
        cid = first.consent_id
        assert cid == again.consent_id  # un solo consentimiento vigente por propósito
        with pytest.raises(ValidationFailed):
            svc.grant(uid, ConsentPurpose.exact_geometry, "  ")
        with pytest.raises(NotFound):
            svc.withdraw(uid, ConsentPurpose.exact_geometry)
    with admin_engine.connect() as c:
        row = c.execute(
            text(
                "SELECT text_version, granted_at, withdrawn_at FROM auth.consent WHERE consent_id=:c"
            ),
            {"c": cid},
        ).one()
    assert (
        row.text_version == "texto-v2" and row.granted_at is not None and row.withdrawn_at is None
    )


def test_assignment_requires_active_analysis_consent(
    app_engine: Engine, admin_engine: Engine, world: World
) -> None:
    newtech = world.f.user("tecnico")
    with unit_of_work(app_engine, world.farmer_b_user["user_id"]) as uow:
        svc = ConsentService(uow)
        svc.assign_technician(
            newtech["user_id"], world.farmer_b
        )  # farmer_b tiene consentimiento 'analysis'
    assert (
        count(
            admin_engine,
            "SELECT count(*) FROM farm.technician_assignment WHERE technician_id=:t",
            t=newtech["user_id"],
        )
        == 1
    )
    world.f.withdraw(world.consent_b)
    other = world.f.user("tecnico")
    with (
        unit_of_work(app_engine, world.farmer_b_user["user_id"]) as uow,
        pytest.raises(ValidationFailed),
    ):
        ConsentService(uow).assign_technician(other["user_id"], world.farmer_b)
