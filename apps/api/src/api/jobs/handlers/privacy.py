"""Handlers de borrado: ``parcel_delete`` y ``consent_purge`` (REALES; no dependen de R1/R2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from api.jobs import purge
from api.jobs.context import JobContext
from api.jobs.registry import register
from api.models.enums import ConsentPurpose, JobKind
from api.repositories.accounts import AuditRepository


@register(JobKind.parcel_delete)
def parcel_delete(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    parcel_id = UUID(payload["parcel_id"])
    s = ctx.uow.session
    ctx.check_cancelled()
    visible = s.execute(
        text("SELECT 1 FROM farm.parcel WHERE parcel_id = :p"), {"p": parcel_id}
    ).first()
    if visible is not None:
        run_ids = purge.run_ids_for_parcel(s, parcel_id)
        art = purge.collect_artifacts(s, run_ids)
        ctx.checkpoint({"v": 1, "stage": "db_pending", **art.as_dict()})
        ctx.progress(0.2)
        purge.purge_run_data(s, run_ids, parcel_id)
        purge.purge_parcel_rows(s, parcel_id)
        AuditRepository(s).record(ctx.created_by, "parcel.delete", "parcel", parcel_id)
        ctx.uow.commit()
        ctx.progress(0.7)
        db_deleted = True
    else:
        db_deleted = False  # ya borrada (reintento) o no visible para el creador
    pending = _load_checkpoint(ctx)
    removed = purge.delete_artifacts(ctx.store, pending) if pending else 0
    return {"v": 1, "parcel_deleted": db_deleted, "files_removed": removed}


def _load_checkpoint(ctx: JobContext) -> purge.Artifacts | None:
    from sqlalchemy.orm import Session

    from api.repositories.jobs import JobRepository

    with Session(ctx.engine) as s:
        job = JobRepository(s).get(ctx.job_id)
        data = job.result if job else None
    if not data or data.get("stage") != "db_pending":
        return None
    return purge.Artifacts.from_dict(data)


@register(JobKind.consent_purge)
def consent_purge(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Aplica el efecto de retirar un consentimiento sobre lo que dependía de él (README §22)."""
    purpose = ConsentPurpose(payload["purpose"])
    s = ctx.uow.session
    parcels = [
        r[0] for r in s.execute(text("SELECT parcel_id FROM farm.parcel"))
    ]  # RLS: las del usuario
    art = purge.Artifacts()
    if purpose is ConsentPurpose.exact_geometry:
        for p in parcels:
            s.execute(text("DELETE FROM private.parcel_geometry WHERE parcel_id = :p"), {"p": p})
    elif purpose is ConsentPurpose.report_sharing:
        rows = s.execute(
            text(
                "DELETE FROM report.report WHERE privacy_level = 'public' "
                "AND (run_id IN (SELECT run_id FROM engine.analysis_run WHERE parcel_id = ANY(:p)) "
                "OR generated_by = :u) RETURNING pdf_uri"
            ),
            {"p": parcels, "u": ctx.created_by},
        )
        art.pdfs = [r[0] for r in rows if r[0]]
    else:  # analysis: resultados y PDFs por parcela hasta la retirada (README §22, retención)
        for p in parcels:
            run_ids = purge.run_ids_for_parcel(s, p)
            a = purge.collect_artifacts(s, run_ids)
            art.result_dirs += a.result_dirs
            art.pdfs += a.pdfs
            purge.purge_run_data(s, run_ids, p)
    AuditRepository(s).record(
        ctx.created_by, "consent.purge", "consent", None, {"purpose": purpose.value}
    )
    ctx.uow.commit()
    removed = purge.delete_artifacts(ctx.store, art)
    return {
        "v": 1,
        "purpose": purpose.value,
        "parcels_affected": len(parcels),
        "files_removed": removed,
    }
