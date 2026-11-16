"""Configuración validada al arrancar (spec R3 §7).

- Falla al iniciar si falta una variable obligatoria (``JWT_SECRET``, ``DATABASE_URL``).
- No hay valores productivos inseguros por defecto.
- Los secretos son ``SecretStr``: nunca aparecen en ``repr``/logs.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "example", "secret")
MIN_JWT_SECRET_LEN = 32
MIN_DISPLAY_GRID_M = 1000  # spec R3 §9.6 / README §13.3: nunca menor a 1 km


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Variables definidas por la especificación (R3 §7) ---------------------------------
    database_url: str = Field(description="Rol de aplicación (sin BYPASSRLS, no propietario).")
    data_dir: Path = Path("./data")
    jwt_secret: SecretStr
    jwt_ttl_minutes: int = Field(default=15, ge=1, le=120)  # valor operativo: [Pendiente] DP
    earthdata_token: SecretStr | None = (
        None  # solo se pasa a la ETL (proceso hijo) si la ingesta está activa
    )
    etl_ingest_enabled: bool = Field(
        default=False,
        description="Permite que el trabajo zone_ingest invoque `milpa-etl` (R1) como proceso. "
        "Requiere red hacia NASA; desactivado en demo/CI.",
    )
    etl_step_timeout_seconds: int = Field(default=3600, ge=60, le=86_400)
    enable_exact_geometry: bool = False
    map_tile_url: str = ""
    map_attribution: str = ""
    max_upload_mb: int = Field(default=2, ge=1, le=64)  # valor operativo: [Pendiente]
    rate_limit_per_min: int = Field(default=120, ge=1)  # valor operativo: [Pendiente]
    milpa_mode: Literal["sandbox", "production"] = "sandbox"
    demo_readonly: bool = False

    # --- Extensiones de R3 (documentadas en ADR) -------------------------------------------
    migration_database_url: str | None = None  # rol propietario; solo Alembic/entrypoint
    jwt_secret_previous: SecretStr | None = None  # rotación de clave (verificación solamente)
    jwt_issuer: str = "milpa-resiliente"
    jwt_audience: str = "milpa-api"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trust_forwarded_for: bool = False
    page_default_limit: int = Field(default=50, ge=1)
    page_max_limit: int = Field(default=100, ge=1)
    display_grid_m: int = Field(default=MIN_DISPLAY_GRID_M, ge=MIN_DISPLAY_GRID_M)  # DP-13
    login_lock_threshold: int = Field(default=5, ge=1)
    login_lock_base_seconds: int = Field(default=60, ge=1)
    login_lock_max_seconds: int = Field(default=900, ge=1)
    job_max_workers: int = Field(default=2, ge=1, le=8)  # spec: 1-2 concurrentes (a medir)
    job_max_attempts: int = Field(default=3, ge=1)
    # Timeout por tipo: [Pendiente]. 0 = sin timeout (no se asumen valores sin decisión).
    job_timeout_seconds: int = Field(default=0, ge=0)
    log_level: str = "INFO"
    web_dist_dir: Path = Path(
        "./apps/web/dist"
    )  # estáticos de R4; se sirven solo si el directorio existe

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _driver(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        if not v.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL debe ser postgresql+psycopg:// (ADR-002)")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        # NoDecode: el valor llega como texto crudo (vacío, "a,b" o JSON) y se interpreta aquí.
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            if text.startswith("["):
                return json.loads(text)
            return [o.strip() for o in text.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _safety(self) -> Settings:
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < MIN_JWT_SECRET_LEN:
            raise ValueError(f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LEN} caracteres")
        if self.milpa_mode == "production" and any(
            m in secret.lower() for m in _PLACEHOLDER_MARKERS
        ):
            raise ValueError("JWT_SECRET parece un valor de ejemplo; no permitido en production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS no admite '*' (spec R3 §22: CORS restringido)")
        if self.enable_exact_geometry:
            raise ValueError(
                "ENABLE_EXACT_GEOMETRY=true no está implementado en el MVP (nivel B). "
                "Ver docs/PRIVACY.md y ADR-015."
            )
        if self.page_default_limit > self.page_max_limit:
            raise ValueError("PAGE_DEFAULT_LIMIT no puede exceder PAGE_MAX_LIMIT")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def jwt_verification_secrets(self) -> list[str]:
        keys = [self.jwt_secret.get_secret_value()]
        if self.jwt_secret_previous is not None:
            keys.append(self.jwt_secret_previous.get_secret_value())
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()  # los campos obligatorios vienen del entorno
