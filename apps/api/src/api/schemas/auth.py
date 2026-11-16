from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.models.enums import UserRole
from api.schemas.common import PROVISIONAL_R3


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=PROVISIONAL_R3)

    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", repr=False
    )
    password: str = Field(min_length=1, max_length=256, repr=False)


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [
                {
                    "access_token": "<jwt>",
                    "token_type": "bearer",
                    "expires_at": "2026-11-14T12:15:00Z",
                    "expires_in": 900,
                    "role": "tecnico",
                }
            ],
        }
    )

    access_token: str = Field(repr=False)
    token_type: str = "bearer"  # noqa: S105 - tipo de esquema OAuth, no una credencial
    expires_at: datetime
    # Aditivos para el cliente de R4 (su borrador de OpenAPI define `Session` con `expires_in` y
    # `role`; ninguna especificación fija este DTO). Ver docs/integration/R4_FRONTEND_CONTRACT.md.
    expires_in: int = Field(ge=1, description="Segundos de vigencia del token")
    role: UserRole
    demo: bool = Field(
        default=False, description="True: sesión pública de demostración (alcance limitado)"
    )


class UserOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            **PROVISIONAL_R3,
            "examples": [
                {
                    "user_id": "0b1d1e24-6c5e-4f43-9d52-3a3c2f4b9b10",
                    "role": "tecnico",
                    "email": "tecnico@example.org",
                }
            ],
        }
    )

    user_id: UUID
    role: UserRole
    email: str
