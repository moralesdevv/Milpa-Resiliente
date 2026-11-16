from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.schemas.common import PROVISIONAL_R3


class ReportCreate(BaseModel):
    """Solicitud de informe. Cuerpo no definido en la spec; la generación depende de R2/R4."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    run_id: UUID
    ranking_id: UUID | None = None
    locale: Literal["es", "es+en"] = "es"
    privacy_level: Literal["internal", "public"] = "internal"


class ReportOut(BaseModel):
    """Forma de ReportDTO (README §15). ``sections``/``annex`` son opacos hasta que R2/R4 los definan."""

    model_config = ConfigDict(json_schema_extra=PROVISIONAL_R3)

    report_id: UUID
    run_id: UUID | None
    locale: Literal["es", "es+en"] | None
    privacy_level: Literal["internal", "public"]
    template_version: str | None
    pdf_url: str | None
    sha256: str | None
    sections: list[dict[str, Any]]
    annex: list[dict[str, Any]]
    generated_at: datetime | None
