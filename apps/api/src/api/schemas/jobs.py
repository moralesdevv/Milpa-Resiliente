from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.models.enums import JobKind, JobStatus
from api.schemas.common import PROVISIONAL_R3


class JobOut(BaseModel):
    """DTO de estado de trabajo (README §15: 'pendiente de congelar')."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [
                {
                    "job_id": "c3f0b7a0-5a31-4a6a-8d0b-2b6f6f0f4b11",
                    "kind": "report",
                    "status": "queued",
                    "progress": None,
                    "result": None,
                    "error": None,
                    "attempts": 0,
                    "created_at": "2026-11-14T12:00:00Z",
                    "started_at": None,
                    "finished_at": None,
                    "location": "/v1/jobs/c3f0b7a0-5a31-4a6a-8d0b-2b6f6f0f4b11",
                }
            ],
        },
    )

    job_id: UUID
    kind: JobKind
    status: JobStatus
    progress: float | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    attempts: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    location: str


class HealthOut(BaseModel):
    """Respuesta de /healthz: sin configuración, versiones ni datos privados."""

    model_config = ConfigDict(
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [{"status": "ok", "db": "ok"}],
        }
    )

    status: str
    db: str
