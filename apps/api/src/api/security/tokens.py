"""JWT Bearer de vida corta (spec R3 §9.3). Valida firma, expiración y claims obligatorios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from api.config import Settings
from api.errors import Unauthenticated
from api.models.enums import UserRole

ALGORITHM = "HS256"  # fijo: nunca se lee del token (evita alg-confusion / "none")
REQUIRED_CLAIMS = ["sub", "role", "exp", "iat", "iss", "aud", "jti"]


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    role: UserRole
    jti: str
    expires_at: datetime


def create_access_token(
    settings: Settings, user_id: UUID, role: UserRole, *, now: datetime | None = None
) -> tuple[str, datetime]:
    now = now or datetime.now(UTC)
    exp = now + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    return token, exp


def decode_access_token(settings: Settings, token: str) -> TokenClaims:
    last_error: Exception | None = None
    for key in settings.jwt_verification_secrets:  # clave actual y, si existe, la anterior
        try:
            data = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={"require": REQUIRED_CLAIMS},
            )
            return TokenClaims(
                user_id=UUID(data["sub"]),
                role=UserRole(data["role"]),
                jti=data["jti"],
                expires_at=datetime.fromtimestamp(data["exp"], tz=UTC),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            last_error = exc
    # Mensaje genérico: no revelar si falló firma, expiración o claims.
    raise Unauthenticated("Token inválido o expirado") from last_error
