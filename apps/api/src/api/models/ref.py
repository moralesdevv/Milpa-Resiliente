"""Espejos de solo lectura de tablas de R1 (prov/ref). R3 no define su semántica (ADR-003)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.contracts.provisional_enums import Evidence, Provenance
from api.db.base import Base


def _values(e: Any) -> list[str]:
    return [m.value for m in e]


ProvenanceType = Enum(Provenance, name="provenance_t", create_type=False, values_callable=_values)
EvidenceType = Enum(Evidence, name="evidence_t", create_type=False, values_callable=_values)


class Citation(Base):
    __tablename__ = "citation"
    __table_args__ = {"schema": "prov"}

    citation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bibkey: Mapped[str] = mapped_column(Text)
    full_text: Mapped[str] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)


class IndicatorProvenance(Base):
    """prov.indicator_provenance. R3 solo inserta filas con evidencia provista por EvidencePort."""

    __tablename__ = "indicator_provenance"
    __table_args__ = {"schema": "prov"}

    ip_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column()
    indicator_code: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    provenance: Mapped[Provenance] = mapped_column(ProvenanceType)
    evidence_level: Mapped[Evidence | None] = mapped_column(EvidenceType)
    source_ids: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    ingestion_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    dataset_version: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    spatial_res_m: Mapped[int | None] = mapped_column(Integer)
    processing_method: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    missing_pct: Mapped[float | None] = mapped_column()
    assumptions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    limitations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    evidence_rule_id: Mapped[str] = mapped_column(Text)


class SoilProperty(Base):
    __tablename__ = "soil_property"
    __table_args__ = {"schema": "ref"}

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    unit: Mapped[str] = mapped_column(Text)
    valid_min: Mapped[float | None] = mapped_column()
    valid_max: Mapped[float | None] = mapped_column()
    accepted_methods: Mapped[list[str]] = mapped_column(ARRAY(Text))
    max_age_years: Mapped[int | None] = mapped_column(SmallInteger)


class Crop(Base):
    __tablename__ = "crop"
    __table_args__ = {"schema": "ref"}

    crop_id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    name_es: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    scientific_name: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str] = mapped_column(Text)
    is_legume: Mapped[bool | None] = mapped_column(Boolean)
    fixes_n_conditions: Mapped[str | None] = mapped_column(Text)


class Strategy(Base):
    __tablename__ = "strategy"
    __table_args__ = {"schema": "ref"}

    strategy_id: Mapped[UUID] = mapped_column(primary_key=True)
    region_id: Mapped[UUID | None] = mapped_column(ForeignKey("geo.region.region_id"))
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    is_reference: Mapped[bool] = mapped_column(Boolean)
    changes_from_reference: Mapped[list[Any]] = mapped_column(ARRAY(Text))


class StrategyVersion(Base):
    __tablename__ = "strategy_version"
    __table_args__ = {"schema": "ref"}

    strategy_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    strategy_id: Mapped[UUID] = mapped_column(ForeignKey("ref.strategy.strategy_id"))
    version: Mapped[int] = mapped_column(Integer)
    catalog_release_id: Mapped[UUID] = mapped_column()
    horizon_years: Mapped[int] = mapped_column(SmallInteger)
    anchor_cycle_idx: Mapped[int] = mapped_column(SmallInteger)
