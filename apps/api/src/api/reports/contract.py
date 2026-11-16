"""Contrato de ENTRADA del servicio PDF de R3.

*** PROVISIONAL (``PROVISIONAL_REPORT_INPUT_V0``) *** — NO es el ``ReportModel`` de R2 (SE-11) ni
``ReportDTO``. Existe para validar y renderizar con la plantilla técnica provisional. Cuando R2
entregue ``ReportModel`` se escribirá un adaptador ``ReportModel -> ReportInput`` (o se reemplazará
este modelo) mediante ADR; R3 no calcula cifras científicas ni genera contenido del informe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CONTRACT_VERSION = "PROVISIONAL_REPORT_INPUT_V0"
TEMPLATE_VERSION = "provisional-technical-v0"

Short = Annotated[str, StringConstraints(max_length=300)]
Long = Annotated[str, StringConstraints(max_length=8000)]


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_es: Short
    title_en: Short | None = None
    body_es: Long
    body_en: Long | None = None
    items: list[Short] = Field(default_factory=list, max_length=100)


class ReferenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Long
    product_version: Short | None = None  # "Referencias con versión del producto" (spec R3 §15.3)


class RunHashes(BaseModel):
    """Identificadores de reproducibilidad de la corrida (spec R3 §16.1)."""

    model_config = ConfigDict(extra="forbid")

    code_version: Short
    region_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    params_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, lt=2**63)


class InternalFields(BaseModel):
    """Solo se renderizan con privacy_level='internal'. Un informe 'public' los rechaza."""

    model_config = ConfigDict(extra="forbid")

    farmer_display_name: Short | None = None
    parcel_code: Short | None = None


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: Literal["es", "es+en"]
    privacy_level: Literal["internal", "public"]
    zone_name: Short  # único identificador territorial permitido en informes públicos
    run_id: UUID | None = None
    hashes: RunHashes
    generated_at: datetime
    summary_es: Long
    summary_en: Long | None = None
    sections: list[ReportSection] = Field(default_factory=list, max_length=50)
    annex: list[ReportSection] = Field(default_factory=list, max_length=50)
    references: list[ReferenceItem] = Field(default_factory=list, max_length=200)
    assumptions: list[Short] = Field(default_factory=list, max_length=100)
    limitations: list[Short] = Field(default_factory=list, max_length=100)
    provenance_notes: list[Short] = Field(default_factory=list, max_length=200)
    internal: InternalFields | None = None
    provisional_banner: bool = True  # la plantilla provisional se rotula siempre

    @model_validator(mode="after")
    def _consistency(self) -> ReportInput:
        if self.locale == "es+en" and not self.summary_en:
            raise ValueError("locale 'es+en' exige summary_en")
        if self.privacy_level == "public" and self.internal is not None:
            raise ValueError("Un informe público no puede incluir campos internos")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at debe incluir zona horaria")
        return self
