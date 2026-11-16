from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.dependencies.core import CtxDep, IdempotencyKey
from api.reports.service import ReportService
from api.routers._common import AUTHED, JobId, ReportId, accepted, error_responses
from api.schemas.jobs import HealthOut, JobOut
from api.schemas.reports import ReportCreate, ReportOut
from api.services.catalog_reports import ReportsApiService, report_out
from api.services.health import database_ok
from api.services.jobs import JobService, to_out

reports_router = APIRouter(prefix="/reports", tags=["reports"])
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
health_router = APIRouter(tags=["health"])


@reports_router.post(
    "",
    response_model=JobOut,
    status_code=202,
    summary="Solicitar informe (trabajo)",
    description="Roles: técnico o dueño de la parcela. La generación del contenido "
    "requiere el modelo de informe de R2 y la plantilla de R4; sin ellos el trabajo "
    "termina en `failed` con `DEPENDENCY_NOT_INTEGRATED`.",
    responses={**AUTHED, **error_responses(404, 409, 422)},
)
def create_report(
    body: ReportCreate, ctx: CtxDep, response: Response, idempotency_key: IdempotencyKey = None
) -> JobOut:
    job, _ = ReportsApiService(ctx).request(body, idempotency_key)
    return accepted(job, response)


@reports_router.get(
    "/{id}",
    response_model=ReportOut,
    summary="Metadatos del informe",
    responses={**AUTHED, **error_responses(404)},
)
def get_report(report_id: ReportId, ctx: CtxDep) -> ReportOut:
    return report_out(ReportService(ctx).get(report_id))


@reports_router.get(
    "/{id}/pdf",
    response_class=Response,
    summary="Descargar PDF (verifica SHA-256)",
    responses={
        200: {
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "description": "PDF",
        },
        **AUTHED,
        **error_responses(404),
    },
)
def download_pdf(report_id: ReportId, ctx: CtxDep) -> Response:
    pdf = ReportService(ctx).read_pdf(report_id)
    return Response(
        content=pdf.data,
        media_type="application/pdf",
        headers={
            "ETag": f'"{pdf.sha256}"',
            "X-Content-SHA256": pdf.sha256,
            "Content-Disposition": f'attachment; filename="informe-{report_id}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@jobs_router.get(
    "/{id}",
    response_model=JobOut,
    summary="Estado, progreso, resultado o error",
    description="Roles: creador o admin.",
    responses={**AUTHED, **error_responses(404)},
)
def get_job(job_id: JobId, ctx: CtxDep) -> JobOut:
    return to_out(JobService(ctx).get(job_id))


@jobs_router.delete(
    "/{id}",
    response_model=JobOut,
    summary="Cancelar trabajo",
    description="Roles: creador o admin. `queued` se cancela de inmediato; `running` "
    "se cancela de forma cooperativa (el handler abandona en su siguiente "
    "comprobación y su resultado se descarta). Un trabajo terminado no cambia.",
    responses={**AUTHED, **error_responses(404)},
)
def cancel_job(job_id: JobId, ctx: CtxDep) -> JobOut:
    return to_out(JobService(ctx).cancel(job_id))


@health_router.get(
    "/healthz",
    response_model=HealthOut,
    summary="Salud de la aplicación y de la base de datos",
    description="Público. No expone configuración, versiones ni datos.",
    responses={503: {"description": "Base de datos no disponible"}},
)
def healthz(request: Request, response: Response) -> HealthOut:
    if database_ok(request.app.state.engine):
        return HealthOut(status="ok", db="ok")
    response.status_code = 503
    return HealthOut(status="degraded", db="unavailable")
