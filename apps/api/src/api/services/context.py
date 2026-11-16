"""Contexto de servicio: unidad de trabajo con RLS, usuario autenticado y puertos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from api.adapters.ports import Ports
from api.config import Settings
from api.db.uow import UnitOfWork
from api.errors import Forbidden
from api.models.enums import UserRole
from api.storage.object_store import ObjectStore

if TYPE_CHECKING:
    from api.jobs.dispatch import JobDispatcher


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    role: UserRole
    email: str = ""

    def require_role(self, *roles: UserRole) -> None:
        if self.role not in roles:
            raise Forbidden("Su rol no permite esta operación")


@dataclass
class ServiceContext:
    uow: UnitOfWork
    user: CurrentUser
    settings: Settings
    ports: Ports
    store: ObjectStore
    dispatcher: JobDispatcher

    @property
    def session(self) -> Session:
        return self.uow.session
