from __future__ import annotations

from fastapi import APIRouter

from api.dependencies.core import CtxDep, CurrentUserDep, SettingsDep, UowDep
from api.routers._common import AUTHED, error_responses
from api.schemas.auth import LoginRequest, TokenResponse, UserOut
from api.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Inicio de sesión",
    description="Devuelve un JWT Bearer de vida corta. Tras varios intentos fallidos la cuenta se "
    "bloquea de forma progresiva. El mensaje de error es el mismo para usuario inexistente, "
    "contraseña errónea, cuenta bloqueada o deshabilitada.",
    responses=error_responses(401, 422, 429),
)
def login(body: LoginRequest, uow: UowDep, settings: SettingsDep) -> TokenResponse:
    result = AuthService(uow, settings).login(body.email, body.password)
    return TokenResponse(
        access_token=result.token,
        expires_at=result.expires_at,
        expires_in=settings.jwt_ttl_minutes * 60,
        role=result.role,
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Perfil del usuario autenticado",
    description="Roles: cualquiera autenticado.",
    responses=AUTHED,
)
def me(user: CurrentUserDep, ctx: CtxDep) -> UserOut:
    return UserOut(user_id=user.user_id, role=user.role, email=user.email)
