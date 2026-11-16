"""Persistencia de cuentas, consentimientos, asignaciones y bitácora de auditoría."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from api.models.auth import AppUser, AuditLog, Consent
from api.models.farm import Farmer, TechnicianAssignment


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def by_email(self, email: str) -> AppUser | None:
        return self.s.scalar(select(AppUser).where(AppUser.email == email.strip().lower()))

    def by_id(self, user_id: UUID) -> AppUser | None:
        return self.s.get(AppUser, user_id)

    def register_failed_login(
        self, user_id: UUID, count: int, locked_until: datetime | None
    ) -> None:
        self.s.execute(
            update(AppUser)
            .where(AppUser.user_id == user_id)
            .values(
                failed_login_count=count,
                last_failed_login_at=datetime.now(UTC),
                locked_until=locked_until,
            )
        )

    def clear_failed_logins(self, user_id: UUID) -> None:
        self.s.execute(
            update(AppUser)
            .where(AppUser.user_id == user_id)
            .values(failed_login_count=0, locked_until=None)
        )


class ConsentRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def active(self, subject_user_id: UUID, purpose: str) -> Consent | None:
        return self.s.scalar(
            select(Consent).where(
                Consent.subject_user_id == subject_user_id,
                Consent.purpose == purpose,
                Consent.withdrawn_at.is_(None),
            )
        )

    def grant(self, subject_user_id: UUID, purpose: str, text_version: str) -> Consent:
        consent = Consent(
            subject_user_id=subject_user_id,
            purpose=purpose,
            text_version=text_version,
            granted_at=datetime.now(UTC),
        )
        self.s.add(consent)
        self.s.flush()
        return consent

    def withdraw(self, consent: Consent) -> None:
        consent.withdrawn_at = datetime.now(UTC)
        self.s.flush()


class FarmerRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def by_user(self, user_id: UUID) -> Farmer | None:
        return self.s.scalar(select(Farmer).where(Farmer.user_id == user_id))

    def by_id(self, farmer_id: UUID) -> Farmer | None:
        return self.s.get(Farmer, farmer_id)


class AssignmentRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def active_for(self, technician_id: UUID, farmer_id: UUID) -> TechnicianAssignment | None:
        return self.s.scalar(
            select(TechnicianAssignment).where(
                TechnicianAssignment.technician_id == technician_id,
                TechnicianAssignment.farmer_id == farmer_id,
                TechnicianAssignment.revoked_at.is_(None),
            )
        )

    def assign(
        self, technician_id: UUID, farmer_id: UUID, consent_id: UUID
    ) -> TechnicianAssignment:
        existing = self.s.get(TechnicianAssignment, (technician_id, farmer_id))
        if existing is not None:
            existing.consent_id = consent_id
            existing.revoked_at = None
            existing.assigned_at = datetime.now(UTC)
            self.s.flush()
            return existing
        row = TechnicianAssignment(
            technician_id=technician_id, farmer_id=farmer_id, consent_id=consent_id
        )
        self.s.add(row)
        self.s.flush()
        return row

    def revoke(self, technician_id: UUID, farmer_id: UUID) -> None:
        row = self.s.get(TechnicianAssignment, (technician_id, farmer_id))
        if row is not None:
            row.revoked_at = datetime.now(UTC)
            self.s.flush()


class AuditRepository:
    """Bitácora mínima: solo identificadores técnicos y fecha (spec R3 §9.7). Nada personal."""

    def __init__(self, session: Session) -> None:
        self.s = session

    def record(
        self,
        actor: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.s.add(
            AuditLog(
                actor_user_id=actor,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
            )
        )
        self.s.flush()
