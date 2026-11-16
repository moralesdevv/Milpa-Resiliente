"""Sistema de trabajos (BE-04): estados, idempotencia, cancelación, reintentos, recuperación, pool real."""

from __future__ import annotations

import threading
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from api.jobs.context import JobContext, RetryableJobError
from api.jobs.dispatch import InlineDispatcher, NullDispatcher, ProcessPoolDispatcher, WorkerConfig
from api.jobs.recovery import recover_jobs
from api.jobs.registry import override_handler
from api.jobs.worker import SAFE_INTERNAL_MESSAGE, run_job
from api.models.enums import JobKind, JobStatus
from api.repositories.jobs import JobRepository
from testkit.app import World


@pytest.fixture
def dispatcher(worker_config: WorkerConfig) -> InlineDispatcher:
    return InlineDispatcher(worker_config)


def new_job(
    engine: Engine,
    kind: JobKind,
    payload: dict[str, Any] | None = None,
    user: UUID | None = None,
    key: str | None = None,
    status: JobStatus = JobStatus.queued,
    attempts: int = 0,
) -> UUID:
    with Session(engine) as s:
        job, _ = JobRepository(s).create(kind, payload or {"v": 1}, user, key)
        job.status, job.attempts = status, attempts
        s.commit()
        return job.job_id


def state(engine: Engine, job_id: UUID) -> dict[str, Any]:
    with Session(engine) as s:
        j = JobRepository(s).get(job_id)
        assert j is not None
        return {
            "status": j.status,
            "progress": j.progress,
            "result": j.result,
            "error": j.error,
            "attempts": j.attempts,
            "started": j.started_at,
            "finished": j.finished_at,
        }


@pytest.fixture
def handler_patch() -> Any:
    saved: list[tuple[JobKind, Any]] = []

    def patch(kind: JobKind, fn: Any) -> None:
        saved.append((kind, override_handler(kind, fn)))

    yield patch
    for kind, prev in reversed(saved):
        override_handler(kind, prev)


def test_lifecycle_queued_running_ok_with_progress(
    app_engine: Engine, worker_config: WorkerConfig, world: World, handler_patch: Any
) -> None:
    seen: dict[str, Any] = {}

    def handler(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        seen["status_inside"] = state(ctx.engine, ctx.job_id)["status"]
        ctx.progress(0.5)
        seen["progress_inside"] = state(ctx.engine, ctx.job_id)["progress"]
        # el handler corre con el contexto RLS de su creador
        seen["visible_parcels"] = [
            r[0] for r in ctx.uow.session.execute(text("SELECT code FROM farm.parcel"))
        ]
        return {"v": 1, "echo": payload["v"]}

    handler_patch(JobKind.report, handler)
    jid = new_job(app_engine, JobKind.report, user=world.farmer_a_user["user_id"])
    assert state(app_engine, jid)["status"] == JobStatus.queued
    run_job(jid, worker_config)
    st = state(app_engine, jid)
    assert st["status"] == JobStatus.ok and st["progress"] == 1.0 and st["attempts"] == 1
    assert (
        st["result"] == {"v": 1, "echo": 1}
        and st["started"]
        and st["finished"]
        and st["error"] is None
    )
    assert seen == {
        "status_inside": JobStatus.running,
        "progress_inside": 0.5,
        "visible_parcels": ["PARCELA-A"],
    }


def test_handler_error_is_persisted_without_leaking_exception_text(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    def boom(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("fallo con persona@example.org y 14.51234567,-89.51234567")

    handler_patch(JobKind.report, boom)
    jid = new_job(app_engine, JobKind.report)
    run_job(jid, worker_config)
    st = state(app_engine, jid)
    assert st["status"] == JobStatus.failed and st["error"]["code"] == "JOB_FAILED"
    assert st["error"]["type"] == "ValueError" and st["error"]["message"] == SAFE_INTERNAL_MESSAGE
    blob = str(st["error"])
    assert "persona@example.org" not in blob and "14.51234567" not in blob


def test_dependency_not_integrated_is_a_typed_job_failure(
    app_engine: Engine, worker_config: WorkerConfig
) -> None:
    for kind, payload in [
        (JobKind.analysis_run, {"v": 1}),
        (JobKind.zone_ingest, {"v": 1, "zone_id": str(uuid4())}),
    ]:
        jid = new_job(app_engine, kind, payload)
        run_job(jid, worker_config)
        st = state(app_engine, jid)
        assert st["status"] == JobStatus.failed
        assert st["error"]["code"] == "DEPENDENCY_NOT_INTEGRATED" and st["result"] is None


def test_retryable_error_is_retried_until_success(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    calls = {"n": 0}

    def flaky(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RetryableJobError
        return {"v": 1, "attempt": ctx.attempt}

    handler_patch(JobKind.report, flaky)
    jid = new_job(app_engine, JobKind.report)
    run_job(jid, worker_config)
    st = state(app_engine, jid)
    assert (
        st["status"] == JobStatus.ok
        and st["attempts"] == 2
        and st["result"] == {"v": 1, "attempt": 2}
    )


def test_retries_are_bounded_by_max_attempts(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    def always(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        raise RetryableJobError

    handler_patch(JobKind.report, always)
    jid = new_job(app_engine, JobKind.report)
    run_job(jid, worker_config)
    st = state(app_engine, jid)
    assert st["status"] == JobStatus.failed and st["attempts"] == worker_config.max_attempts


def test_claim_is_atomic_under_concurrency(app_engine: Engine) -> None:
    jid = new_job(app_engine, JobKind.report)
    winners: list[bool] = []

    def claim() -> None:
        with Session(app_engine) as s:
            got = JobRepository(s).claim(jid) is not None
            s.commit()
            winners.append(got)

    threads = [threading.Thread(target=claim) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert winners.count(True) == 1 and state(app_engine, jid)["attempts"] == 1


def test_finished_job_cannot_be_resurrected_or_rerun(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    runs = {"n": 0}

    def once(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        runs["n"] += 1
        return {"v": 1}

    handler_patch(JobKind.report, once)
    jid = new_job(app_engine, JobKind.report)
    run_job(jid, worker_config)
    run_job(jid, worker_config)  # duplicado del despacho: no vuelve a ejecutar
    assert runs["n"] == 1 and state(app_engine, jid)["attempts"] == 1


# ----------------------------------------------------------------------- cancelación
def test_cancel_queued_via_api_then_worker_noop(
    client: TestClient,
    login: Any,
    app_engine: Engine,
    worker_config: WorkerConfig,
    world: World,
    handler_patch: Any,
) -> None:
    ran = {"n": 0}
    handler_patch(JobKind.report, lambda c, p: ran.update(n=ran["n"] + 1) or {"v": 1})
    jid = new_job(app_engine, JobKind.report, user=world.tech["user_id"])
    h = login(world.tech)
    r = client.delete(f"/v1/jobs/{jid}", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    run_job(jid, worker_config)
    assert ran["n"] == 0 and state(app_engine, jid)["status"] == JobStatus.cancelled
    again = client.delete(f"/v1/jobs/{jid}", headers=h)  # idempotente
    assert again.status_code == 200 and again.json()["status"] == "cancelled"


def test_cancel_running_is_cooperative_and_result_is_discarded(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    started, proceed = threading.Event(), threading.Event()
    jid_box: dict[str, UUID] = {}

    def slow(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        started.set()
        proceed.wait(5)
        ctx.check_cancelled()  # debe lanzar JobCancelled
        return {"v": 1, "should": "not be stored"}

    handler_patch(JobKind.report, slow)
    jid_box["id"] = new_job(app_engine, JobKind.report)
    t = threading.Thread(target=run_job, args=(jid_box["id"], worker_config))
    t.start()
    assert started.wait(5)
    with Session(app_engine) as s:
        JobRepository(s).cancel(jid_box["id"])
        s.commit()
    proceed.set()
    t.join(10)
    st = state(app_engine, jid_box["id"])
    assert st["status"] == JobStatus.cancelled and st["result"] is None


def test_finished_job_is_not_changed_by_cancel(
    client: TestClient, login: Any, app_engine: Engine, world: World
) -> None:
    jid = new_job(app_engine, JobKind.report, user=world.tech["user_id"], status=JobStatus.ok)
    r = client.delete(f"/v1/jobs/{jid}", headers=login(world.tech))
    assert r.json()["status"] == "ok"


# ----------------------------------------------------------------------- idempotencia y visibilidad
ZONE_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [[-89.55, 14.45], [-89.45, 14.45], [-89.45, 14.55], [-89.55, 14.55], [-89.55, 14.45]]
    ],
}


def post_zone(
    client: TestClient,
    headers: dict[str, str],
    world: World,
    key: str | None = None,
    name: str = "Zona nueva",
    geometry: Any = None,
) -> Any:
    h = dict(headers)
    if key:
        h["Idempotency-Key"] = key
    return client.post(
        "/v1/zones",
        headers=h,
        json={"region_id": str(world.region), "name": name, "geometry": geometry or ZONE_GEOM},
    )


def test_zone_creation_returns_202_location_and_runs_job(
    client: TestClient, login: Any, world: World, dispatcher: InlineDispatcher
) -> None:
    r = post_zone(client, login(world.tech), world)
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    assert r.headers["Location"] == f"/v1/jobs/{jid}"
    got = client.get(f"/v1/jobs/{jid}", headers=login(world.tech)).json()
    # ingestión de R1 no integrada: el trabajo (en línea) terminó con error tipado, sin datos inventados
    assert (
        got["kind"] == "zone_ingest"
        and got["status"] == "failed"
        and got["error"]["code"] == "DEPENDENCY_NOT_INTEGRATED"
    )


def test_idempotency_key_prevents_duplicate_jobs_and_zones(
    client: TestClient, login: Any, world: World, admin_engine: Engine
) -> None:
    h = login(world.tech)
    a = post_zone(client, h, world, key="clave-123")
    b = post_zone(client, h, world, key="clave-123")
    assert a.status_code == b.status_code == 202 and a.json()["job_id"] == b.json()["job_id"]
    with admin_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM engine.job")).scalar_one() == 1
        assert (
            c.execute(text("SELECT count(*) FROM geo.zone WHERE name='Zona nueva'")).scalar_one()
            == 1
        )
    other = post_zone(
        client, login(world.admin), world, key="clave-123"
    )  # misma clave, otro usuario
    assert other.status_code == 202 and other.json()["job_id"] != a.json()["job_id"]
    assert post_zone(client, h, world, key="mala clave!").status_code == 422


def test_idempotency_key_reuse_on_different_operation_conflicts(
    client: TestClient, login: Any, world: World, dispatcher: Any
) -> None:
    h = login(world.farmer_a_user)
    first = client.delete(f"/v1/parcels/{world.parcel_a}", headers={**h, "Idempotency-Key": "k-1"})
    assert first.status_code == 202
    other_parcel = world.f.parcel(world.farmer_a, world.zone, "SEGUNDA")
    second = client.delete(f"/v1/parcels/{other_parcel}", headers={**h, "Idempotency-Key": "k-1"})
    assert second.status_code == 409 and second.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_job_visibility_creator_and_admin_only(
    client: TestClient, login: Any, app_engine: Engine, world: World
) -> None:
    jid = new_job(app_engine, JobKind.report, user=world.tech["user_id"])
    assert client.get(f"/v1/jobs/{jid}", headers=login(world.tech)).status_code == 200
    assert client.get(f"/v1/jobs/{jid}", headers=login(world.admin)).status_code == 200
    assert client.get(f"/v1/jobs/{jid}", headers=login(world.farmer_b_user)).status_code == 404
    assert client.delete(f"/v1/jobs/{jid}", headers=login(world.farmer_b_user)).status_code == 404
    assert client.get(f"/v1/jobs/{jid}").status_code == 401
    assert client.get(f"/v1/jobs/{uuid4()}", headers=login(world.tech)).status_code == 404


def test_zone_validation_and_roles(client: TestClient, login: Any, world: World) -> None:
    assert post_zone(client, login(world.farmer_a_user), world).status_code == 403
    bowtie = {
        "type": "Polygon",
        "coordinates": [
            [[-89.55, 14.45], [-89.45, 14.55], [-89.45, 14.45], [-89.55, 14.55], [-89.55, 14.45]]
        ],
    }
    assert post_zone(client, login(world.tech), world, geometry=bowtie).status_code == 422
    outside = {
        "type": "Polygon",
        "coordinates": [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]],
    }
    assert post_zone(client, login(world.tech), world, geometry=outside).status_code == 422
    assert (
        post_zone(
            client, login(world.tech), world, geometry={"type": "Point", "coordinates": [0, 0]}
        ).status_code
        == 422
    )


# ----------------------------------------------------------------------- recuperación tras reinicio
def test_orphan_recovery_requeues_idempotent_and_fails_the_rest(app_engine: Engine) -> None:
    requeue = new_job(app_engine, JobKind.report, status=JobStatus.running, attempts=1)
    exhausted = new_job(app_engine, JobKind.analysis_run, status=JobStatus.running, attempts=3)
    not_idem = new_job(app_engine, JobKind.zone_ingest, status=JobStatus.running, attempts=1)
    queued = new_job(app_engine, JobKind.parcel_delete, status=JobStatus.queued)
    done = new_job(app_engine, JobKind.report, status=JobStatus.ok)
    d = NullDispatcher()
    rep = recover_jobs(app_engine, d, max_attempts=3)
    assert (rep.requeued, rep.failed, rep.redispatched) == (1, 2, 2)
    assert state(app_engine, requeue)["status"] == JobStatus.queued
    assert state(app_engine, requeue)["error"]["code"] == "ORPHANED_REQUEUED"
    assert state(app_engine, exhausted)["status"] == JobStatus.failed
    assert state(app_engine, not_idem)["status"] == JobStatus.failed
    assert state(app_engine, not_idem)["error"]["code"] == "ORPHANED"
    assert (
        set(d.submitted) == {requeue, queued} and state(app_engine, done)["status"] == JobStatus.ok
    )


def test_recovered_job_runs_to_completion(
    app_engine: Engine, worker_config: WorkerConfig, handler_patch: Any
) -> None:
    handler_patch(JobKind.report, lambda c, p: {"v": 1, "recovered": True})
    jid = new_job(app_engine, JobKind.report, status=JobStatus.running, attempts=1)
    recover_jobs(app_engine, InlineDispatcher(worker_config), max_attempts=3)
    st = state(app_engine, jid)
    assert (
        st["status"] == JobStatus.ok
        and st["attempts"] == 2
        and st["result"] == {"v": 1, "recovered": True}
    )


def test_app_startup_runs_recovery(app_engine: Engine, settings: Any, ports: Any) -> None:
    from api.main import create_app

    jid = new_job(app_engine, JobKind.report, status=JobStatus.running, attempts=0)
    d = NullDispatcher()
    with TestClient(
        create_app(settings, engine=app_engine, ports=ports, dispatcher=d, recover_on_start=True)
    ):
        pass
    assert jid in d.submitted and state(app_engine, jid)["status"] == JobStatus.queued


# ----------------------------------------------------------------------- pool de procesos real
@pytest.mark.slow
def test_process_pool_runs_job_in_a_separate_process(
    app_engine: Engine, admin_engine: Engine, worker_config: WorkerConfig, world: World
) -> None:
    """Un worker spawn crea su propio Engine; el borrado se completa fuera del proceso de pruebas."""
    jid = new_job(
        app_engine,
        JobKind.parcel_delete,
        {"v": 1, "parcel_id": str(world.parcel_a)},
        user=world.farmer_a_user["user_id"],
    )
    pool = ProcessPoolDispatcher(worker_config, max_workers=1)
    try:
        pool.submit(jid)
        import time

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and state(app_engine, jid)["status"] in (
            JobStatus.queued,
            JobStatus.running,
        ):
            time.sleep(0.5)
    finally:
        pool.shutdown()
    st = state(app_engine, jid)
    assert st["status"] == JobStatus.ok, st
    assert st["result"]["parcel_deleted"] is True
    with admin_engine.connect() as c:  # propietario: la comprobación no depende de RLS
        assert (
            c.execute(
                text("SELECT count(*) FROM farm.parcel WHERE parcel_id=:p"), {"p": world.parcel_a}
            ).scalar_one()
            == 0
        )
