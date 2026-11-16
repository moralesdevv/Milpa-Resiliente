"""Servicio de informes: valida -> renderiza -> PDF -> guarda -> SHA-256 -> registra -> verifica."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from api.errors import ApiError, ErrorCode, NotFound
from api.models.report import Report
from api.reports.contract import TEMPLATE_VERSION, ReportInput
from api.reports.pdf import render_pdf
from api.repositories.analysis import ReportRepository
from api.services.context import ServiceContext
from api.storage.object_store import ObjectStore


class ReportIntegrityError(ApiError):
    status, code, title = (
        500,
        ErrorCode.INTEGRITY_CHECK_FAILED,
        "Falló la verificación de integridad",
    )


@dataclass(frozen=True)
class PdfFile:
    data: bytes
    sha256: str


def pdf_path(report_id: UUID) -> str:
    return f"reports/{report_id}.pdf"


class ReportService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.repo = ReportRepository(ctx.session)

    @property
    def store(self) -> ObjectStore:
        return self.ctx.store

    def generate(self, data: ReportInput, *, ranking_id: UUID | None = None) -> Report:
        """Genera y registra el PDF (ReportLab, Python puro) a partir de una entrada validada."""
        report_id = uuid4()
        # Lanza PublicReportPrivacyError si un informe público filtra datos; ReportRenderError si falla el dibujo.
        pdf = render_pdf(data)
        sha = self.store.write_bytes(pdf_path(report_id), pdf)
        pdf_uri = pdf_path(report_id)
        if hashlib.sha256(pdf).hexdigest() != sha:  # verificación tras escribir
            self.store.delete(pdf_path(report_id))
            raise ReportIntegrityError("El PDF escrito no coincide con el generado")
        report = Report(
            report_id=report_id,
            run_id=data.run_id,
            ranking_id=ranking_id,
            locale=data.locale,
            template_version=TEMPLATE_VERSION,
            privacy_level=data.privacy_level,
            content_json=data.model_dump(mode="json"),
            pdf_uri=pdf_uri,
            pdf_sha256=sha,
            generated_by=self.ctx.user.user_id,
        )
        self.repo.add(report)
        self.ctx.uow.commit()
        return report

    def get(self, report_id: UUID) -> Report:
        report = self.repo.get(report_id)  # RLS: invisible => None
        if report is None:
            raise NotFound("Informe no encontrado")
        return report

    def read_pdf(self, report_id: UUID) -> PdfFile:
        """Devuelve el PDF verificando su SHA-256 contra el registrado."""
        report = self.get(report_id)
        if not report.pdf_uri or not report.pdf_sha256:
            raise NotFound("El informe aún no tiene PDF")
        if not self.store.exists(report.pdf_uri):
            raise NotFound("El archivo PDF no está disponible")
        with self.store.open_read(report.pdf_uri) as fh:
            data = fh.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != report.pdf_sha256:
            raise ReportIntegrityError("El PDF almacenado no coincide con su hash registrado")
        return PdfFile(data, digest)
