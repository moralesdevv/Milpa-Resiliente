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


@router.post(
    "/demo-session",
    response_model=TokenResponse,
    summary="Sesión pública de demostración",
    description="Sin credenciales. Solo si el servidor habilita `DEMO_PUBLIC_ACCESS`. El token es de una "
    "cuenta sin parcelas ni contraseña utilizable y su alcance está limitado a lectura de resultados y a "
    "crear corridas de zona, escenarios, rankings e informes (todo lo demás responde 403).",
    responses=error_responses(404, 429, 503),
)
def demo_session(uow: UowDep, settings: SettingsDep) -> TokenResponse:
    result = AuthService(uow, settings).demo_session()
    return TokenResponse(
        access_token=result.token,
        expires_at=result.expires_at,
        expires_in=settings.demo_ttl_minutes * 60,
        role=result.role,
        demo=True,
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
