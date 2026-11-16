"""Errores de dominio y formato único de error (RFC 7807 ampliado, README §15).

Los códigos de la especificación se declaran en ``ErrorCode``. Los marcados como
*extensión R3* no están en la lista del README §15/§10.3 y requieren aprobación
(ver ADR-010); se usan solo para condiciones de infraestructura sin equivalente.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ERROR_TYPE_BASE = "https://milpa.local/errors/"


class ErrorCode(StrEnum):
    # --- definidos por la especificación integral ---
    MIXED_CYCLE_LENGTH = "MIXED_CYCLE_LENGTH"
    MULTIPLE_SWEEP_CYCLES = "MULTIPLE_SWEEP_CYCLES"
    MISSING_THRESHOLD_CITATION = "MISSING_THRESHOLD_CITATION"
    INSUFFICIENT_SOIL_DATA = "INSUFFICIENT_SOIL_DATA"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    RUN_NOT_READY = "RUN_NOT_READY"
    SCENARIO_NOT_COMPUTED = "SCENARIO_NOT_COMPUTED"
    CSV_VALIDATION_FAILED = "CSV_VALIDATION_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    # --- extensión R3 (pendiente de aprobación, ADR-010) ---
    DEPENDENCY_NOT_INTEGRATED = "DEPENDENCY_NOT_INTEGRATED"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    DATASET_INCOMPATIBLE = "DATASET_INCOMPATIBLE"
    INTEGRITY_CHECK_FAILED = "INTEGRITY_CHECK_FAILED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    READ_ONLY_MODE = "READ_ONLY_MODE"
    INVALID_CURSOR = "INVALID_CURSOR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiError(Exception):
    status: int = 500
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    title: str = "Error interno"

    def __init__(
        self,
        detail: str | None = None,
        *,
        hint: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
        code: ErrorCode | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.hint = hint
        self.errors = errors or []
        self.headers = headers or {}
        if code is not None:
            self.code = code


class BadRequest(ApiError):
    status, code, title = 400, ErrorCode.VALIDATION_ERROR, "Solicitud mal formada"


class Unauthenticated(ApiError):
    status, code, title = 401, ErrorCode.UNAUTHENTICATED, "No autenticado"

    def __init__(self, detail: str | None = None, **kw: Any) -> None:
        kw.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(detail, **kw)


class Forbidden(ApiError):
    status, code, title = 403, ErrorCode.FORBIDDEN, "Acceso denegado"


class NotFound(ApiError):
    """404 también para recursos existentes pero no visibles (anti-enumeración, spec §10.3)."""

    status, code, title = 404, ErrorCode.NOT_FOUND, "Recurso no encontrado"


class Conflict(ApiError):
    status, code, title = 409, ErrorCode.RUN_NOT_READY, "Conflicto de estado"


class PayloadTooLarge(ApiError):
    status, code, title = 413, ErrorCode.PAYLOAD_TOO_LARGE, "Contenido demasiado grande"


class UnsupportedMediaType(ApiError):
    status, code, title = 415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Tipo de contenido no admitido"


class ValidationFailed(ApiError):
    status, code, title = 422, ErrorCode.VALIDATION_ERROR, "Error de validación"


class RateLimited(ApiError):
    status, code, title = 429, ErrorCode.RATE_LIMITED, "Demasiadas solicitudes"


class ServiceUnavailable(ApiError):
    status, code, title = 503, ErrorCode.DEPENDENCY_NOT_INTEGRATED, "Servicio no disponible"


class DependencyNotIntegrated(ServiceUnavailable):
    """Un módulo de otro rol (R1/R2/R4) aún no está integrado. Nunca se simulan resultados."""

    code = ErrorCode.DEPENDENCY_NOT_INTEGRATED
    title = "Dependencia no integrada"

    def __init__(self, component: str, capability: str, **kw: Any) -> None:
        kw.setdefault(
            "hint",
            f"Pendiente de entrega/integración de {component}. Ver docs/integration/INTEGRATION_STATUS.md",
        )
        super().__init__(f"{capability} no está disponible: {component} no integrado.", **kw)
        self.component = component


def problem_type(code: ErrorCode | str) -> str:
    return ERROR_TYPE_BASE + str(code).lower().replace("_", "-")
