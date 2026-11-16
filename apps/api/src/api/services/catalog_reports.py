"""Catálogos (lectura de ref.*, propiedad de R1) y endpoints de informe (POST/GET)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from api.errors import NotFound
from api.models.enums import ConsentPurpose, JobKind, UserRole
from api.pagination import slice_page
from api.repositories.analysis import CatalogRepository
from api.schemas.catalog import (
    CropOut,
    ReferenceOut,
    StrategyComponentOut,
    StrategyCycleOut,
    StrategyOut,
    StrategyVersionOut,
)
from api.schemas.common import Page
from api.schemas.reports import ReportCreate, ReportOut
from api.services.access import AccessPolicy
from api.services.context import ServiceContext
from api.services.jobs import JobService
from api.services.runs import RunService


class CatalogService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.repo = CatalogRepository(ctx.session)
        self.settings = ctx.settings

    def crops(self, cursor: str | None, limit: int | None) -> Page[CropOut]:
        rows, nxt = slice_page(self.repo.crops(), lambda c: c.code, cursor, limit, self.settings)
        return Page[CropOut](items=[CropOut.model_validate(c) for c in rows], next_cursor=nxt)

    def strategies(self, cursor: str | None, limit: int | None) -> Page[StrategyOut]:
        rows, nxt = slice_page(
            self.repo.strategies(), lambda s: s.code, cursor, limit, self.settings
        )
        latest = self.repo.latest_versions()
        items = [
            StrategyOut(
                latest_version=latest.get(s.strategy_id),
                strategy_id=s.strategy_id,
                code=s.code,
                name=s.name,
                is_reference=s.is_reference,
                changes_from_reference=[str(x) for x in (s.changes_from_reference or [])],
            )
            for s in rows
        ]
        return Page[StrategyOut](items=items, next_cursor=nxt)

    def strategy_version(self, strategy_id: UUID, version: int) -> StrategyVersionOut:
        sv = self.repo.strategy_version(strategy_id, version)
        if sv is None:
            raise NotFound("Versión de estrategia no encontrada")
        cycles = [
            StrategyCycleOut(
                **{k: v for k, v in c.items() if k != "components"},
                components=[StrategyComponentOut(**k) for k in c["components"]],
            )
            for c in self.repo.cycles(sv.strategy_version_id)
        ]
        return StrategyVersionOut(
            strategy_version_id=sv.strategy_version_id,
            strategy_id=sv.strategy_id,
            version=sv.version,
            horizon_years=sv.horizon_years,
            anchor_cycle_idx=sv.anchor_cycle_idx,
            cycles=cycles,
        )

    def references(self, cursor: str | None, limit: int | None) -> Page[ReferenceOut]:
        rows, nxt = slice_page(
            self.repo.references(), lambda c: c.bibkey, cursor, limit, self.settings
        )
        return Page[ReferenceOut](
            items=[ReferenceOut.model_validate(c) for c in rows], next_cursor=nxt
        )


class ReportsApiService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.access = AccessPolicy(ctx)

    def request(self, body: ReportCreate, key: str | None) -> tuple[Any, bool]:
        """Crea el trabajo de generación (202). Roles: técnico o dueño de la parcela."""
        self.ctx.user.require_role(UserRole.tecnico, UserRole.agricultor, UserRole.admin)
        run = RunService(self.ctx).visible_run(body.run_id)  # 404 si no accede
        if run.parcel_id is not None:
            parcel = self.access.parcel(self.ctx.user, run.parcel_id)
            self.access.require_consent_for_parcel(parcel, ConsentPurpose.analysis)
            if body.privacy_level == "public":
                self.access.require_consent_for_parcel(parcel, ConsentPurpose.report_sharing)
        elif self.ctx.user.role == UserRole.agricultor:
            raise NotFound("Corrida no encontrada")
        payload = body.model_dump(mode="json")
        return JobService(self.ctx).submit(JobKind.report, payload, key)


def report_out(report: Any) -> ReportOut:
    content = report.content_json or {}
    has_pdf = bool(report.pdf_uri and report.pdf_sha256)
    return ReportOut(
        report_id=report.report_id,
        run_id=report.run_id,
        locale=report.locale,
        privacy_level=report.privacy_level,
        template_version=report.template_version,
        pdf_url=f"/v1/reports/{report.report_id}/pdf" if has_pdf else None,
        sha256=report.pdf_sha256,
        sections=list(content.get("sections", [])),
        annex=list(content.get("annex", [])),
        generated_at=report.generated_at,
    )
