"""Autorización por pertenencia (no solo por rol). RLS es la segunda barrera (spec R3 §9.2/§9.4).

La comprobación explícita de aquí es independiente de la política SQL: si ambas discrepan, el
acceso se niega (404, anti-enumeración).
"""

from __future__ import annotations

from uuid import UUID

from api.errors import ErrorCode, Forbidden, NotFound
from api.models.enums import ConsentPurpose, UserRole
from api.models.farm import Parcel
from api.repositories.accounts import AssignmentRepository, ConsentRepository, FarmerRepository
from api.repositories.farms import ParcelRepository
from api.services.context import CurrentUser, ServiceContext


class ConsentRequired(Forbidden):
    code = ErrorCode.CONSENT_REQUIRED
    title = "Consentimiento requerido"


class AccessPolicy:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.farmers = FarmerRepository(ctx.session)
        self.assignments = AssignmentRepository(ctx.session)
        self.consents = ConsentRepository(ctx.session)
        self.parcels = ParcelRepository(ctx.session)

    # -- pertenencia a un agricultor ------------------------------------------------------------
    def can_access_farmer(self, user: CurrentUser, farmer_id: UUID | None) -> bool:
        if farmer_id is None or user.role == UserRole.admin:
            return False  # el admin no obtiene acceso automático a contenido privado
        farmer = self.farmers.by_id(farmer_id)
        if farmer is None:
            return False
        if user.role == UserRole.agricultor:
            return farmer.user_id == user.user_id
        if farmer.user_id is None:
            return False
        return (
            self.assignments.active_for(user.user_id, farmer_id) is not None
            and self.consents.active(farmer.user_id, ConsentPurpose.analysis.value) is not None
        )

    def parcel(self, user: CurrentUser, parcel_id: UUID, *, owner_only: bool = False) -> Parcel:
        parcel = self.parcels.get(parcel_id)  # RLS: invisible => None
        if parcel is None or not self.can_access_farmer(user, parcel.farmer_id):
            raise NotFound("Parcela no encontrada")
        if owner_only and not self._is_owner(user, parcel):
            raise NotFound("Parcela no encontrada")
        return parcel

    def _is_owner(self, user: CurrentUser, parcel: Parcel) -> bool:
        farmer = self.farmers.by_user(user.user_id)
        return farmer is not None and parcel.farmer_id == farmer.farmer_id

    # -- consentimiento (bloquea NUEVOS usos al retirarse) -----------------------------------------
    def require_consent_for_farmer(self, farmer_id: UUID, purpose: ConsentPurpose) -> None:
        farmer = self.farmers.by_id(farmer_id)
        subject = farmer.user_id if farmer else None
        if subject is None or self.consents.active(subject, purpose.value) is None:
            raise ConsentRequired(
                f"No hay consentimiento vigente para el propósito '{purpose.value}'",
                hint="El agricultor debe otorgar o renovar su consentimiento.",
            )

    def require_consent_for_parcel(self, parcel: Parcel, purpose: ConsentPurpose) -> None:
        if parcel.farmer_id is None:
            raise ConsentRequired("La parcela no tiene agricultor asociado")
        self.require_consent_for_farmer(parcel.farmer_id, purpose)
