"""RLS con el rol REAL de aplicación y dos (o más) usuarios (spec R3 §9.4, §21.2).

Estas pruebas hablan SQL directamente (sin la capa Python de autorización): demuestran que la base
de datos protege los datos aunque un endpoint contenga un error.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from api.db.uow import unit_of_work
from testkit.app import World

PARCELS = "SELECT code FROM farm.parcel ORDER BY code"


def codes(engine: Engine, user_id: UUID | None, sql: str = PARCELS) -> list[str]:
    with unit_of_work(engine, user_id) as uow:
        return [r[0] for r in uow.session.execute(text(sql))]


def test_each_farmer_sees_only_own_parcels(app_engine: Engine, world: World) -> None:
    assert codes(app_engine, world.farmer_a_user["user_id"]) == ["PARCELA-A"]
    assert codes(app_engine, world.farmer_b_user["user_id"]) == ["PARCELA-B"]


def test_no_context_means_no_rows(app_engine: Engine, world: World) -> None:
    assert codes(app_engine, None) == []  # sin SET LOCAL app.user_id => falla segura


def test_assigned_technician_sees_only_assigned_farmers_parcels(
    app_engine: Engine, world: World
) -> None:
    assert codes(app_engine, world.tech["user_id"]) == ["PARCELA-A"]
    assert codes(app_engine, world.tech_unassigned["user_id"]) == []


def test_admin_has_no_automatic_access_to_private_data(app_engine: Engine, world: World) -> None:
    assert codes(app_engine, world.admin["user_id"]) == []
    assert codes(app_engine, world.admin["user_id"], "SELECT display_name FROM farm.farmer") == []


def test_withdrawn_consent_revokes_technician_visibility(app_engine: Engine, world: World) -> None:
    assert codes(app_engine, world.tech["user_id"]) == ["PARCELA-A"]
    world.f.withdraw(world.consent_a)
    assert codes(app_engine, world.tech["user_id"]) == []
    assert codes(app_engine, world.farmer_a_user["user_id"]) == [
        "PARCELA-A"
    ]  # el dueño conserva acceso


def test_revoked_assignment_revokes_visibility(
    app_engine: Engine, world: World, admin_engine: Engine
) -> None:
    with admin_engine.connect() as c:
        c.execute(text("UPDATE farm.technician_assignment SET revoked_at = now()"))
    assert codes(app_engine, world.tech["user_id"]) == []


def test_consent_for_other_purpose_does_not_grant_access(
    app_engine: Engine, world: World, admin_engine: Engine
) -> None:
    other = world.f.user("tecnico")
    c_report = world.f.consent(world.farmer_b_user, "report_sharing")
    world.f.assign(other, world.farmer_b, c_report)  # consentimiento de propósito equivocado
    assert codes(app_engine, other["user_id"]) == []


def test_context_does_not_leak_between_transactions_on_same_connection(
    world: World, test_db
) -> None:  # type: ignore[no-untyped-def]
    """pool_size=1: la MISMA conexión física sirve a usuarios distintos y a 'nadie'."""
    engine = create_engine(test_db.app_url, pool_size=1, max_overflow=0)
    try:
        assert codes(engine, world.farmer_a_user["user_id"]) == ["PARCELA-A"]
        assert codes(engine, None) == []  # misma conexión, sin contexto: nada residual
        assert codes(engine, world.farmer_b_user["user_id"]) == ["PARCELA-B"]
        with engine.connect() as c:  # y sin transacción de usuario, la variable está vacía
            assert c.execute(text("SELECT current_setting('app.user_id', true)")).scalar() in (
                None,
                "",
            )
    finally:
        engine.dispose()


def test_set_local_is_cleared_by_commit_not_only_rollback(world: World, test_db) -> None:  # type: ignore[no-untyped-def]
    engine = create_engine(test_db.app_url, pool_size=1, max_overflow=0)
    try:
        with unit_of_work(engine, world.farmer_a_user["user_id"]) as uow:
            uow.session.execute(text("SELECT 1"))
            uow.session.commit()  # commit sin reaplicar
            cur = uow.session.execute(text("SELECT current_setting('app.user_id', true)")).scalar()
            assert cur in (None, ""), "SET LOCAL no puede sobrevivir al commit"
            assert [r[0] for r in uow.session.execute(text(PARCELS))] == []
    finally:
        engine.dispose()


def test_insert_into_other_users_farmer_is_rejected_by_policy(
    app_engine: Engine, world: World
) -> None:
    with (
        unit_of_work(app_engine, world.farmer_b_user["user_id"]) as uow,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        uow.session.execute(
            text("INSERT INTO farm.parcel (zone_id, farmer_id, code) VALUES (:z, :f, 'INTRUSA')"),
            {"z": world.zone, "f": world.farmer_a},
        )


def test_update_and_delete_of_foreign_parcel_affect_zero_rows(
    app_engine: Engine, world: World, admin_engine: Engine
) -> None:
    with unit_of_work(app_engine, world.farmer_b_user["user_id"]) as uow:
        r1 = uow.session.execute(
            text("UPDATE farm.parcel SET code='X' WHERE parcel_id=:p"), {"p": world.parcel_a}
        )
        r2 = uow.session.execute(
            text("DELETE FROM farm.parcel WHERE parcel_id=:p"), {"p": world.parcel_a}
        )
        assert r1.rowcount == 0 and r2.rowcount == 0  # type: ignore[attr-defined]
        uow.session.commit()
    with admin_engine.connect() as c:
        assert (
            c.execute(
                text("SELECT code FROM farm.parcel WHERE parcel_id=:p"), {"p": world.parcel_a}
            ).scalar_one()
            == "PARCELA-A"
        )


def test_technician_cannot_delete_parcel_only_owner(app_engine: Engine, world: World) -> None:
    with unit_of_work(app_engine, world.tech["user_id"]) as uow:
        res = uow.session.execute(
            text("DELETE FROM farm.parcel WHERE parcel_id=:p"), {"p": world.parcel_a}
        )
        assert res.rowcount == 0  # type: ignore[attr-defined]


def test_soil_data_is_protected_and_view_respects_rls(app_engine: Engine, world: World) -> None:
    world.f.soil_property("ph")
    world.f.sample_with_measurement(world.parcel_a, "ph", 6.1)
    own = codes(
        app_engine,
        world.farmer_a_user["user_id"],
        "SELECT property_code FROM soil.property_status WHERE status='medido'",
    )
    other = codes(
        app_engine,
        world.farmer_b_user["user_id"],
        "SELECT property_code FROM soil.property_status WHERE status='medido'",
    )
    assert own == ["ph"] and other == []
    assert codes(
        app_engine, world.farmer_b_user["user_id"], "SELECT count(*)::text FROM soil.measurement"
    ) == ["0"]
    assert codes(
        app_engine, world.tech["user_id"], "SELECT count(*)::text FROM soil.measurement"
    ) == ["1"]


def test_private_exact_geometry_visible_only_to_owner(
    app_engine: Engine, world: World, admin_engine: Engine
) -> None:
    with admin_engine.connect() as c:
        c.execute(
            text(
                "INSERT INTO private.parcel_geometry (parcel_id, exact_geom, consent_id) VALUES "
                "(:p, ST_GeomFromText('POLYGON((-89.5 14.5,-89.49 14.5,-89.49 14.51,-89.5 14.5))',4326), :c)"
            ),
            {"p": world.parcel_a, "c": world.consent_a},
        )
    sql = "SELECT parcel_id::text FROM private.parcel_geometry"
    assert codes(app_engine, world.farmer_a_user["user_id"], sql) == [str(world.parcel_a)]
    assert codes(app_engine, world.tech["user_id"], sql) == []  # ni el técnico asignado
    assert codes(app_engine, world.farmer_b_user["user_id"], sql) == []


def test_reports_visible_to_generator_or_parcel_access_only(
    app_engine: Engine, world: World, admin_engine: Engine
) -> None:
    with admin_engine.connect() as c:
        c.execute(
            text(
                "INSERT INTO report.report (privacy_level, content_json, generated_by) VALUES ('internal','{}', :u)"
            ),
            {"u": world.farmer_a_user["user_id"]},
        )
    sql = "SELECT count(*)::text FROM report.report"
    assert codes(app_engine, world.farmer_a_user["user_id"], sql) == ["1"]
    assert codes(app_engine, world.farmer_b_user["user_id"], sql) == ["0"]
    assert codes(app_engine, world.admin["user_id"], sql) == ["0"]


def test_sql_injection_through_user_id_is_impossible(app_engine: Engine) -> None:
    """El contexto solo acepta UUID tipados: nada de cadenas arbitrarias en SET LOCAL."""
    from api.db.uow import UnitOfWork

    uow = UnitOfWork(app_engine)
    try:
        with pytest.raises(TypeError):
            uow.set_user("x'; DROP TABLE farm.parcel; --")  # type: ignore[arg-type]
    finally:
        uow.close()
