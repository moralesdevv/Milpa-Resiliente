from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, SmallInteger, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base
from api.models.enums import UserRole

UserRoleType = Enum(
    UserRole, name="user_role_t", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(UserRoleType)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # nunca incluir correo ni hash en registros
        return f"AppUser(user_id={self.user_id}, role={self.role})"


class Consent(Base):
    __tablename__ = "consent"
    __table_args__ = {"schema": "auth"}

    consent_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    subject_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth.app_user.user_id"))
    purpose: Mapped[str] = mapped_column(Text)
    text_version: Mapped[str] = mapped_column(Text)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auth"}

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_user_id: Mapped[UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[UUID | None] = mapped_column()
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
