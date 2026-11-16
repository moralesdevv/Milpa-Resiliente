"""Traducción de los errores tipados de ``milpa_core`` (R2) a los códigos de la API (README §10, §15).

Se resuelve por NOMBRE de clase, sin importar ``milpa_core`` (que aún no existe): así R3 no queda
acoplada a su jerarquía. Un error desconocido NO se traduce (se propaga como error interno).
"""

from __future__ import annotations

from api.errors import ApiError, ErrorCode

# README §10 "Errores tipados": MixedCycleLengthError, MissingThresholdCitation,
# InsufficientSoilData, NotComparable -> códigos de §15. Todos son errores de dominio (422).
_ENGINE_ERRORS: dict[str, ErrorCode] = {
    "MixedCycleLengthError": ErrorCode.MIXED_CYCLE_LENGTH,
    "MissingThresholdCitation": ErrorCode.MISSING_THRESHOLD_CITATION,
    "InsufficientSoilData": ErrorCode.INSUFFICIENT_SOIL_DATA,
    "NotComparable": ErrorCode.NOT_COMPARABLE,
}


class EngineDomainError(ApiError):
    status = 422
    title = "Error de dominio del motor"


def translate_engine_error(exc: BaseException) -> ApiError | None:
    code = _ENGINE_ERRORS.get(type(exc).__name__)
    if code is None:
        return None
    # El texto de R2 es de dominio científico (sin datos personales por contrato); se trunca.
    return EngineDomainError(str(exc)[:500] or code.value, code=code)
