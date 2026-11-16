"""Dependencias FastAPI: configuración, unidad de trabajo con RLS, autenticación y contexto."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.adapters.ports import Ports
from api.config import Settings
from api.db.uow import UnitOfWork
from api.errors import Forbidden, Unauthenticated
from api.jobs.dispatch import JobDispatcher
from api.repositories.accounts import UserRepository
from api.security.demo import demo_allows
from api.security.ratelimit import SlidingWindowLimiter
from api.security.tokens import decode_access_token
from api.services.context import CurrentUser, ServiceContext
from api.storage.object_store import ObjectStore

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT de vida corta obtenido en POST /v1/auth/login. Authorization: Bearer <token>",
)


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_uow(request: Request) -> Iterator[UnitOfWork]:
    uow = UnitOfWork(request.app.state.engine)
    try:
        yield uow
    finally:
        uow.close()  # rollback de lo no confirmado + devolución limpia al pool


SettingsDep = Annotated[Settings, Depends(get_settings)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_current_user(
    request: Request,
    uow: UowDep,
    settings: SettingsDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthenticated("Se requiere autenticación")
    claims = decode_access_token(settings, creds.credentials)
    if claims.demo and not demo_allows(request.method, request.url.path):
        raise Forbidden("La sesión de demostración no permite esta operación")
    user = UserRepository(uow.session).by_id(claims.user_id)
    if user is None or user.disabled_at is not None:
        raise Unauthenticated("Token inválido o expirado")
    uow.set_user(user.user_id)  # SET LOCAL app.user_id dentro de la transacción de la solicitud
    limiter: SlidingWindowLimiter = request.app.state.user_limiter
    limiter.check(str(user.user_id))
    return CurrentUser(user_id=user.user_id, role=user.role, email=user.email)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_ctx(
    request: Request, uow: UowDep, user: CurrentUserDep, settings: SettingsDep
) -> ServiceContext:
    state = request.app.state
    ports: Ports = state.ports
    store: ObjectStore = state.store
    dispatcher: JobDispatcher = state.dispatcher
    return ServiceContext(
        uow=uow, user=user, settings=settings, ports=ports, store=store, dispatcher=dispatcher
    )


CtxDep = Annotated[ServiceContext, Depends(get_ctx)]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description="Evita duplicar la creación de trabajos (1-128 caracteres).",
    ),
]
