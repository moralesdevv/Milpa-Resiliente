"""Inicio de sesión con bloqueo progresivo (spec R3 §9.3). Mensajes genéricos (anti-enumeración)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from api.config import Settings
from api.db.uow import UnitOfWork
from api.errors import NotFound, ServiceUnavailable, Unauthenticated
from api.models.auth import AppUser
from api.models.enums import UserRole
from api.repositories.accounts import UserRepository
from api.security.passwords import verify_password
from api.security.tokens import create_access_token

GENERIC_FAILURE = "Credenciales inválidas"


@dataclass(frozen=True)
class LoginResult:
    token: str
    expires_at: datetime
    role: UserRole


def lock_duration(failures: int, settings: Settings) -> timedelta | None:
    """Bloqueo progresivo: 0 bajo el umbral; luego base·2^(n-umbral), con tope máximo."""
    over = failures - settings.login_lock_threshold
    if over < 0:
        return None
    seconds = min(
        settings.login_lock_base_seconds * (2 ** min(over, 20)), settings.login_lock_max_seconds
    )
    return timedelta(seconds=seconds)


class AuthService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self.uow, self.settings = uow, settings
        self.users = UserRepository(uow.session)

    def login(self, email: str, password: str, *, now: datetime | None = None) -> LoginResult:
        now = now or datetime.now(UTC)
        user = self.users.by_email(email)
        locked = user is not None and user.locked_until is not None and user.locked_until > now
        # Siempre se verifica contra un hash (real o ficticio): el tiempo no revela si existe.
        ok = verify_password(password, user.password_hash if user and not locked else None)
        if not ok or user is None or locked or user.disabled_at is not None:
            if user is not None and not locked and user.disabled_at is None:
                self._register_failure(user, now)
            raise Unauthenticated(GENERIC_FAILURE)
        if user.failed_login_count or user.locked_until:
            self.users.clear_failed_logins(user.user_id)
            self.uow.commit()
        token, expires_at = create_access_token(self.settings, user.user_id, user.role, now=now)
        return LoginResult(token, expires_at, user.role)

    def demo_session(self, *, now: datetime | None = None) -> LoginResult:
        """Token de alcance limitado para la cuenta de demostración (sin contraseña utilizable)."""
        if not self.settings.demo_public_access:
            raise NotFound("El acceso público de demostración no está habilitado")
        user = self.users.by_email(self.settings.demo_user_email)
        if user is None or user.disabled_at is not None:
            raise ServiceUnavailable(
                "La cuenta de demostración no está aprovisionada (python -m api.cli create-demo-user)"
            )
        token, expires_at = create_access_token(
            self.settings, user.user_id, user.role, now=now, demo=True
        )
        return LoginResult(token, expires_at, user.role)

    def _register_failure(self, user: AppUser, now: datetime) -> None:
        count = min(user.failed_login_count + 1, 32_000)
        wait = lock_duration(count, self.settings)
        self.users.register_failed_login(user.user_id, count, now + wait if wait else None)
        self.uow.commit()  # el contador debe persistir aunque la solicitud falle con 401
