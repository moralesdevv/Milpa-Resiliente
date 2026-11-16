"""Parcelas, suelo (estado, CSV, declaraciones) y perfil de prioridades."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from api.errors import (
    DependencyNotIntegrated,
    NotFound,
    ValidationFailed,
)
from api.models.enums import ConsentPurpose, JobKind, UserRole
from api.models.farm import Parcel
from api.repositories.accounts import FarmerRepository
from api.repositories.farms import ParcelRepository, ProfileRepository, SoilRepository
from api.schemas.parcels import (
    DisplayLocation,
    ParcelCreate,
    ParcelOut,
    PriorityProfileIn,
    PriorityProfileOut,
    SoilCsvResult,
    SoilDeclarationIn,
    SoilDeclarationOut,
    SoilPropertyStatusOut,
    SoilValue,
)
from api.services.access import AccessPolicy
from api.services.context import ServiceContext
from api.services.jobs import JobService
from api.soil_csv import (
    CONTRACT as CSV_CONTRACT,
)
from api.soil_csv import (
    PropertySpec,
    accepted_by_property,
    parse_soil_csv,
)


class ParcelService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.access = AccessPolicy(ctx)
        self.parcels = ParcelRepository(ctx.session)
        self.farmers = FarmerRepository(ctx.session)

    # -- alta -----------------------------------------------------------------------------------
    def create(self, body: ParcelCreate) -> ParcelOut:
        user = self.ctx.user
        user.require_role(UserRole.agricultor, UserRole.tecnico)
        if user.role == UserRole.agricultor:
            own = self.farmers.by_user(user.user_id)
            if own is None:
                raise NotFound("No existe un perfil de agricultor para su cuenta")
            if body.farmer_id not in (None, own.farmer_id):
                raise NotFound("Agricultor no encontrado")
            farmer_id = own.farmer_id
        else:
            if body.farmer_id is None:
                raise ValidationFailed("Los técnicos deben indicar farmer_id")
            farmer_id = body.farmer_id
        if not self.access.can_access_farmer(user, farmer_id):
            raise NotFound("Agricultor no encontrado")  # anti-enumeración
        self.access.require_consent_for_farmer(farmer_id, ConsentPurpose.analysis)

        grid = self.ctx.settings.display_grid_m
        gen = self.parcels.generalize(body.zone_id, body.location.lat, body.location.lon, grid)
        if gen is None:
            raise NotFound("Zona no encontrada")
        if not gen.covered:
            raise ValidationFailed("La ubicación indicada no está dentro de la zona")
        parcel = self.parcels.add(
            zone_id=body.zone_id,
            farmer_id=farmer_id,
            code=body.code,
            area_ha=body.area_ha,
            center=gen,
            grid_m=grid,
            created_by=user.user_id,
        )
        self.ctx.uow.commit()
        return self._out(parcel)

    def _out(self, parcel: Parcel) -> ParcelOut:
        loc = self.parcels.display_location(parcel.parcel_id)
        return ParcelOut(
            parcel_id=parcel.parcel_id,
            zone_id=parcel.zone_id,
            farmer_id=parcel.farmer_id,
            code=parcel.code,
            area_ha=parcel.area_ha,
            display_location=DisplayLocation(lat=loc[0], lon=loc[1]) if loc else None,
            display_grid_m=parcel.display_grid_m,
            created_at=parcel.created_at,
        )

    def get(self, parcel_id: UUID) -> ParcelOut:
        return self._out(self.access.parcel(self.ctx.user, parcel_id))

    def request_delete(self, parcel_id: UUID, idempotency_key: str | None) -> tuple[Any, bool]:
        # Solo el dueño (spec: dueño/admin 'según política aprobada'; la ruta admin queda bloqueada
        # hasta aprobar el acceso excepcional registrado: ADR-015, DP-13).
        self.access.parcel(self.ctx.user, parcel_id, owner_only=True)
        return JobService(self.ctx).submit(
            JobKind.parcel_delete, {"parcel_id": str(parcel_id)}, idempotency_key
        )


class SoilService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.access = AccessPolicy(ctx)
        self.repo = SoilRepository(ctx.session)

    def status(self, parcel_id: UUID) -> list[SoilPropertyStatusOut]:
        self.access.parcel(self.ctx.user, parcel_id)
        today = date.today()
        out: list[SoilPropertyStatusOut] = []
        for r in self.repo.status_rows(parcel_id):
            status = r["status"]
            value = None
            method = r["method"]
            if (
                status in ("medido", "desactualizado", "no_representativo")
                and r["m_value"] is not None
            ):
                value = SoilValue(value=r["m_value"], unit=r["unit"], ip_id=r["m_ip"])
            elif status == "declarado" and r["d_value"] is not None:
                value, method = (
                    SoilValue(value=r["d_value"], unit=r["d_unit"], ip_id=r["d_ip"]),
                    None,
                )
            sampled = r["sampled_at"] if status != "declarado" else None
            out.append(
                SoilPropertyStatusOut(
                    property_code=r["property_code"],
                    status=status,
                    value=value,
                    method=method,
                    depth_cm=(r["depth_from_cm"], r["depth_to_cm"]) if sampled else None,
                    sampled_at=sampled,
                    representativeness=r["representativeness"] if sampled else None,
                    age_years=round((today - sampled).days / 365.25, 2) if sampled else None,
                    max_age_years=r["max_age_years"],
                )
            )
        return out

    def _catalog(self) -> dict[str, PropertySpec]:
        return {
            code: PropertySpec(code, p.unit, p.valid_min, p.valid_max, tuple(p.accepted_methods))
            for code, p in self.repo.properties().items()
        }

    def upload_csv(self, parcel_id: UUID, raw: bytes, *, dry_run: bool) -> SoilCsvResult:
        parcel = self.access.parcel(self.ctx.user, parcel_id)
        self.access.require_consent_for_parcel(parcel, ConsentPurpose.analysis)
        catalog = self._catalog()
        rows = parse_soil_csv(  # 422 CSV_VALIDATION_FAILED
            raw, catalog, today=date.today(), parcel_code=parcel.code
        )
        counts = accepted_by_property(rows)
        if dry_run:
            return SoilCsvResult(
                contract=CSV_CONTRACT,
                rows_total=len(rows),
                rows_accepted=len(rows),
                accepted_by_property=counts,
                persisted=False,
                dry_run=True,
            )
        evidence = self.ctx.ports.evidence
        if not evidence.is_available():
            # No se inventa el nivel de evidencia A/B/C (lo decide R2): validar sí, guardar no.
            raise DependencyNotIntegrated(
                evidence.component,
                "El guardado de mediciones (requiere reglas de evidencia)",
                hint="Use ?dry_run=true para validar sin guardar. Ver INTEGRATION_STATUS.md",
            )
        for row in rows:
            sample_id = self.repo.add_sample(
                parcel_id, row.sampled_at, row.lab, row.depth_from_cm, row.depth_to_cm
            )
            for m in row.measurements:
                rec = evidence.provenance_for_soil(
                    kind="medido",
                    property_code=m.code,
                    unit=m.unit,
                    method=m.method,
                    representativeness=row.representativeness,
                )
                ip_id = self.repo.insert_provenance(
                    rec, kind="medido", indicator_code=m.code, unit=m.unit
                )
                self.repo.add_measurement(
                    sample_id, m.code, m.value, m.unit, m.method, row.representativeness, ip_id
                )
        self.ctx.uow.commit()
        return SoilCsvResult(
            contract=CSV_CONTRACT,
            rows_total=len(rows),
            rows_accepted=len(rows),
            accepted_by_property=counts,
            persisted=True,
            dry_run=False,
        )

    def declare(self, parcel_id: UUID, code: str, body: SoilDeclarationIn) -> SoilDeclarationOut:
        parcel = self.access.parcel(self.ctx.user, parcel_id)
        self.access.require_consent_for_parcel(parcel, ConsentPurpose.analysis)
        prop = self.repo.properties().get(code)
        if prop is None:
            raise NotFound("Propiedad de suelo no encontrada")
        if body.unit is not None and body.unit != prop.unit:
            raise ValidationFailed(f"La unidad debe ser '{prop.unit}' para {code}")
        if (prop.valid_min is not None and body.value < prop.valid_min) or (
            prop.valid_max is not None and body.value > prop.valid_max
        ):
            raise ValidationFailed(
                f"Valor fuera del rango válido [{prop.valid_min}, {prop.valid_max}]"
            )
        evidence = self.ctx.ports.evidence
        if not evidence.is_available():
            raise DependencyNotIntegrated(
                evidence.component, "El guardado de declaraciones de suelo"
            )
        rec = evidence.provenance_for_soil(
            kind="declarado",
            property_code=code,
            unit=prop.unit,
            method=None,
            representativeness=None,
        )
        ip_id = self.repo.insert_provenance(
            rec, kind="declarado", indicator_code=code, unit=prop.unit
        )
        row = self.repo.upsert_declaration(
            parcel_id=parcel_id,
            code=code,
            value=body.value,
            unit=prop.unit,
            basis=body.basis,
            declared_by=self.ctx.user.user_id,
            ip_id=ip_id,
        )
        self.ctx.uow.commit()
        return SoilDeclarationOut(
            parcel_id=parcel_id,
            property_code=code,
            value=row.value,
            unit=row.unit,
            basis=row.basis,
            declared_at=row.declared_at or datetime.now(UTC),
            ip_id=row.ip_id,
        )


class ProfileService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.access = AccessPolicy(ctx)
        self.repo = ProfileRepository(ctx.session)

    def save(self, parcel_id: UUID, body: PriorityProfileIn) -> PriorityProfileOut:
        parcel = self.access.parcel(self.ctx.user, parcel_id)
        self.access.require_consent_for_parcel(parcel, ConsentPurpose.analysis)
        profile = self.repo.upsert(
            parcel_id,
            {
                "w_water": body.w_water,
                "w_soil": body.w_soil,
                "w_food": body.w_food,
                "w_income": body.w_income,
            },
            body.constraints,
        )
        self.ctx.uow.commit()
        return PriorityProfileOut(
            parcel_id=parcel_id,
            w_water=profile.w_water,
            w_soil=profile.w_soil,
            w_food=profile.w_food,
            w_income=profile.w_income,
            constraints=profile.constraints,
            updated_at=profile.updated_at,
        )
