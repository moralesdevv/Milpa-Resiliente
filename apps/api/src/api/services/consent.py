"""Consentimiento por propósito, asignación de técnicos y retirada (spec R3 §9.5).

No hay endpoints HTTP para estas operaciones: el contrato no está definido (ADR-010). Se exponen
como servicio, usadas por la CLI de administración y por las pruebas. Retirar un consentimiento:
  * bloquea de inmediato los nuevos usos (las comprobaciones exigen un consentimiento vigente y las
    políticas RLS dejan de ver al técnico);
  * encola el trabajo ``consent_purge`` con lo que dependía de él.
"""

from __future__ import annotations

from uuid import UUID

from api.db.uow import UnitOfWork
from api.errors import NotFound, ValidationFailed
from api.jobs.dispatch import JobDispatcher
from api.models.auth import Consent
from api.models.enums import ConsentPurpose, JobKind
from api.repositories.accounts import (
    AssignmentRepository,
    AuditRepository,
    ConsentRepository,
    FarmerRepository,
)
from api.repositories.jobs import JobRepository


class ConsentService:
    def __init__(self, uow: UnitOfWork, dispatcher: JobDispatcher | None = None) -> None:
        self.uow = uow
        self.dispatcher = dispatcher
        s = uow.session
        self.consents, self.assignments = ConsentRepository(s), AssignmentRepository(s)
        self.farmers, self.audit, self.jobs = (
            FarmerRepository(s),
            AuditRepository(s),
            JobRepository(s),
        )

    def grant(self, subject_user_id: UUID, purpose: ConsentPurpose, text_version: str) -> Consent:
        if not text_version.strip():
            raise ValidationFailed("Se requiere la versión del texto de consentimiento")
        active = self.consents.active(subject_user_id, purpose.value)
        if active is not None:
            return active
        consent = self.consents.grant(subject_user_id, purpose.value, text_version)
        self.audit.record(
            subject_user_id,
            "consent.grant",
            "consent",
            consent.consent_id,
            {"purpose": purpose.value},
        )
        self.uow.commit()
        return consent

    def withdraw(self, subject_user_id: UUID, purpose: ConsentPurpose) -> UUID:
        """Retira el consentimiento y encola la limpieza. Devuelve el job_id de ``consent_purge``."""
        consent = self.consents.active(subject_user_id, purpose.value)
        if consent is None:
            raise NotFound("No hay un consentimiento vigente para ese propósito")
        self.consents.withdraw(consent)
        self.audit.record(
            subject_user_id,
            "consent.withdraw",
            "consent",
            consent.consent_id,
            {"purpose": purpose.value},
        )
        job, _ = self.jobs.create(
            JobKind.consent_purge,
            {"v": 1, "subject_user_id": str(subject_user_id), "purpose": purpose.value},
            subject_user_id,
            None,
        )
        self.uow.commit()
        if self.dispatcher is not None:
            self.dispatcher.submit(job.job_id)
        return job.job_id

    def assign_technician(self, technician_id: UUID, farmer_id: UUID) -> None:
        """Asigna un técnico a un agricultor usando el consentimiento 'analysis' vigente del agricultor."""
        farmer = self.farmers.by_id(farmer_id)
        if farmer is None or farmer.user_id is None:
            raise NotFound("Agricultor no encontrado")
        consent = self.consents.active(farmer.user_id, ConsentPurpose.analysis.value)
        if consent is None:
            raise ValidationFailed("El agricultor no tiene consentimiento 'analysis' vigente")
        self.assignments.assign(technician_id, farmer_id, consent.consent_id)
        self.audit.record(farmer.user_id, "assignment.create", "farmer", farmer_id)
        self.uow.commit()

    def revoke_technician(self, technician_id: UUID, farmer_id: UUID) -> None:
        self.assignments.revoke(technician_id, farmer_id)
        self.uow.commit()
