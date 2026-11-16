from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Region(Base):
    """Espejo de solo lectura de geo.region (propiedad R1)."""

    __tablename__ = "region"
    __table_args__ = {"schema": "geo"}

    region_id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)


class Zone(Base):
    """geo.zone (propiedad R1). R3 inserta filas solo vía POST /v1/zones (ADR-003)."""

    __tablename__ = "zone"
    __table_args__ = {"schema": "geo"}

    zone_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    region_id: Mapped[UUID] = mapped_column(ForeignKey("geo.region.region_id"))
    name: Mapped[str] = mapped_column(Text)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False))
    elevation_m: Mapped[float | None] = mapped_column()
    slope_pct: Mapped[float | None] = mapped_column()
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Farmer(Base):
    __tablename__ = "farmer"
    __table_args__ = {"schema": "farm"}

    farmer_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth.app_user.user_id"))
    display_name: Mapped[str] = mapped_column(Text)
    community: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, server_default="es")
    household_size: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Parcel(Base):
    __tablename__ = "parcel"
    __table_args__ = {"schema": "farm"}

    parcel_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("geo.zone.zone_id"))
    farmer_id: Mapped[UUID | None] = mapped_column(ForeignKey("farm.farmer.farmer_id"))
    code: Mapped[str | None] = mapped_column(Text)
    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    display_geom: Mapped[Any | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    display_grid_m: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("auth.app_user.user_id"))


class PriorityProfile(Base):
    __tablename__ = "priority_profile"
    __table_args__ = {"schema": "farm"}

    profile_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parcel_id: Mapped[UUID | None] = mapped_column(ForeignKey("farm.parcel.parcel_id"))
    w_water: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    w_soil: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    w_food: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    w_income: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TechnicianAssignment(Base):
    __tablename__ = "technician_assignment"
    __table_args__ = {"schema": "farm"}

    technician_id: Mapped[UUID] = mapped_column(
        ForeignKey("auth.app_user.user_id"), primary_key=True
    )
    farmer_id: Mapped[UUID] = mapped_column(ForeignKey("farm.farmer.farmer_id"), primary_key=True)
    consent_id: Mapped[UUID] = mapped_column(ForeignKey("auth.consent.consent_id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SoilSample(Base):
    __tablename__ = "sample"
    __table_args__ = {"schema": "soil"}

    sample_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parcel_id: Mapped[UUID] = mapped_column(ForeignKey("farm.parcel.parcel_id"))
    sampled_at: Mapped[date] = mapped_column(Date)
    lab: Mapped[str | None] = mapped_column(Text)
    depth_from_cm: Mapped[int] = mapped_column(SmallInteger)
    depth_to_cm: Mapped[int] = mapped_column(SmallInteger)


class SoilMeasurement(Base):
    __tablename__ = "measurement"
    __table_args__ = {"schema": "soil"}

    measurement_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sample_id: Mapped[UUID] = mapped_column(ForeignKey("soil.sample.sample_id"))
    property_code: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column()
    unit: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    representativeness: Mapped[str] = mapped_column(Text)
    ip_id: Mapped[UUID] = mapped_column()


class SoilDeclaration(Base):
    __tablename__ = "declaration"
    __table_args__ = {"schema": "soil"}

    parcel_id: Mapped[UUID] = mapped_column(ForeignKey("farm.parcel.parcel_id"), primary_key=True)
    property_code: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[float] = mapped_column()
    unit: Mapped[str] = mapped_column(Text)
    basis: Mapped[str] = mapped_column(Text)
    declared_by: Mapped[UUID | None] = mapped_column()
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_id: Mapped[UUID] = mapped_column()
