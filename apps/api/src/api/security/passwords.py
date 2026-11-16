"""Hash de contraseñas con Argon2id (spec R3 §9.3). Nunca se registran contraseñas ni hashes."""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LEN = 12
MAX_PASSWORD_LEN = 256  # evita DoS por contraseñas enormes

# Parámetros por defecto de argon2-cffi (RFC 9106, perfil de baja memoria); ajustables por ADR.
_hasher = PasswordHasher(type=Type.ID)

# Hash ficticio para igualar el tiempo de respuesta cuando el usuario no existe (anti-enumeración).
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalisation")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return _hasher.hash(password)


def validate_password_policy(password: str) -> None:
    if not (MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN):
        raise ValueError(
            f"La contraseña debe tener entre {MIN_PASSWORD_LEN} y {MAX_PASSWORD_LEN} caracteres"
        )


def verify_password(password: str, password_hash: str | None) -> bool:
    """True si coincide. Con ``password_hash=None`` ejecuta una verificación ficticia."""
    if len(password) > MAX_PASSWORD_LEN:
        return False
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
