from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Date, DateTime, Enum, Float, ForeignKey, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.contracts.provisional_enums import AdaptationMode
from api.db.base import Base
from api.models.enums import JobStatus

JobStatusType = Enum(
    JobStatus,
    name="job_status_t",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)
AdaptationType = Enum(
    AdaptationMode,
    name="adaptation_t",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


class Job(Base):
    """engine.job (README §13.6). Estado de trabajos persistido en PostgreSQL."""

    __tablename__ = "job"
    __table_args__ = {"schema": "engine"}

    job_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(JobStatusType, default=JobStatus.queued)
    progress: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("auth.app_user.user_id"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRun(Base):
    """engine.analysis_run. R3 la lee y la borra; las filas las crea la integración con R2."""

    __tablename__ = "analysis_run"
    __table_args__ = {"schema": "engine"}

    run_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("geo.zone.zone_id"))
    parcel_id: Mapped[UUID | None] = mapped_column(ForeignKey("farm.parcel.parcel_id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(Text)
    mode_reasons: Mapped[list[str]] = mapped_column(ARRAY(Text))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params_hash: Mapped[str] = mapped_column(Text)
    region_config_hash: Mapped[str] = mapped_column(Text)
    catalog_release_id: Mapped[UUID] = mapped_column()
    data_hash: Mapped[str] = mapped_column(Text)
    code_version: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(BigInteger)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)


class ScenarioRun(Base):
    __tablename__ = "scenario_run"
    __table_args__ = {"schema": "engine"}

    run_id: Mapped[UUID] = mapped_column(ForeignKey("engine.analysis_run.run_id"), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(Text, primary_key=True)
    adaptation_mode: Mapped[AdaptationMode] = mapped_column(AdaptationType, primary_key=True)
    status: Mapped[str] = mapped_column(Text)
    results_uri: Mapped[str] = mapped_column(Text)
    results_sha256: Mapped[str | None] = mapped_column(Text)
    n_rows: Mapped[int | None] = mapped_column(BigInteger)
    engine_version: Mapped[str] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
