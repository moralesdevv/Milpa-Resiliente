from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Report(Base):
    __tablename__ = "report"
    __table_args__ = {"schema": "report"}

    report_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("engine.analysis_run.run_id"))
    ranking_id: Mapped[UUID | None] = mapped_column()
    locale: Mapped[str | None] = mapped_column(Text)
    template_version: Mapped[str | None] = mapped_column(Text)
    privacy_level: Mapped[str] = mapped_column(Text)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    pdf_uri: Mapped[str | None] = mapped_column(Text)
    pdf_sha256: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[UUID | None] = mapped_column(ForeignKey("auth.app_user.user_id"))
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
