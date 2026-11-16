"""Zonas, parcelas, perfil de prioridades y suelo. Las tablas privadas están bajo RLS."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from api.adapters.ports import EvidenceRecord
from api.contracts.provisional_enums import Evidence, Provenance
from api.models.farm import (
    Parcel,
    PriorityProfile,
    SoilDeclaration,
    SoilMeasurement,
    SoilSample,
    Zone,
)
from api.models.ref import IndicatorProvenance, SoilProperty


@dataclass(frozen=True)
class Generalized:
    covered: bool
    lat: float
    lon: float


class ZoneRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def page(self, after: tuple[str, UUID] | None, limit: int) -> list[Zone]:
        stmt = select(Zone).order_by(Zone.name, Zone.zone_id).limit(limit + 1)
        if after is not None:
            stmt = stmt.where(tuple_(Zone.name, Zone.zone_id) > tuple_(after[0], after[1]))
        return list(self.s.scalars(stmt))

    def get(self, zone_id: UUID) -> Zone | None:
        return self.s.get(Zone, zone_id)

    def geojson(self, zone_id: UUID) -> dict[str, Any]:
        raw = self.s.execute(
            text("SELECT ST_AsGeoJSON(geom, 5) FROM geo.zone WHERE zone_id = :z"), {"z": zone_id}
        ).scalar_one()
        parsed: dict[str, Any] = json.loads(raw)
        return parsed

    def cells(self, zone_id: UUID) -> list[dict[str, Any]]:
        """Celdas climáticas de la zona con su peso (dato público; nunca una parcela)."""
        rows = self.s.execute(
            text(
                """
                SELECT c.cell_id, s.code AS source, zc.weight,
                       ST_YMin(c.footprint) AS south, ST_XMin(c.footprint) AS west,
                       ST_YMax(c.footprint) AS north, ST_XMax(c.footprint) AS east
                FROM geo.zone_cell zc
                JOIN geo.climate_cell c USING (cell_id)
                JOIN prov.data_source s ON s.source_id = c.source_id
                WHERE zc.zone_id = :z ORDER BY c.cell_id
                """
            ),
            {"z": zone_id},
        ).mappings()
        return [dict(r) for r in rows]

    def sources_by_codes(self, codes: list[str]) -> list[dict[str, Any]]:
        rows = self.s.execute(
            text(
                """
                SELECT s.source_id, s.code, s.product_name, s.institution, s.is_nasa, s.version,
                       s.access_url AS url, c.full_text AS citation
                FROM prov.data_source s LEFT JOIN prov.citation c USING (citation_id)
                WHERE s.code = ANY(:codes) ORDER BY s.source_id
                """
            ),
            {"codes": codes},
        ).mappings()
        return [dict(r) for r in rows]

    def soil_estimates(self, zone_id: UUID) -> list[dict[str, Any]]:
        rows = self.s.execute(
            text(
                "SELECT property_code, depth_label, (value IS NOT NULL) AS available, reason "
                "FROM soil.estimate WHERE zone_id = :z ORDER BY property_code, depth_label"
            ),
            {"z": zone_id},
        ).mappings()
        return [dict(r) for r in rows]

    def create(self, region_id: UUID, name: str, geojson: dict[str, Any]) -> UUID | None:
        """Inserta la zona si la geometría es válida y está dentro de la caja de la región."""
        zone_id = uuid4()
        try:
            with (
                self.s.begin_nested()
            ):  # savepoint: un GeoJSON rechazado por PostGIS no aborta la transacción
                row = self._insert_zone(region_id, name, geojson, zone_id)
        except DBAPIError:
            return None
        return row[0] if row else None

    def _insert_zone(
        self, region_id: UUID, name: str, geojson: dict[str, Any], zone_id: UUID
    ) -> Any:
        return self.s.execute(
            text(
                """
                WITH g AS (
                  SELECT ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)) AS geom
                ), r AS (SELECT bbox FROM geo.region WHERE region_id = :r)
                INSERT INTO geo.zone (zone_id, region_id, name, geom)
                SELECT :z, :r, :n, g.geom FROM g, r
                WHERE ST_IsValid(g.geom) AND ST_Covers(r.bbox, g.geom)
                RETURNING zone_id
                """
            ),
            {"gj": json.dumps(geojson), "r": region_id, "n": name, "z": zone_id},
        ).first()


class ParcelRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def generalize(self, zone_id: UUID, lat: float, lon: float, grid_m: int) -> Generalized | None:
        """Centro de la celda de rejilla (UTM, metros reales) con ST_SnapToGrid.

        El punto original solo viaja como parámetro de esta consulta: no se persiste ni se registra.
        Se usa UTM (no EPSG:3857) para que 1000 m sean ~1000 m reales a cualquier latitud.
        """
        row = self.s.execute(
            text(
                """
                WITH p AS (SELECT ST_SetSRID(ST_MakePoint(CAST(:lon AS double precision),
                                                           CAST(:lat AS double precision)), 4326) AS g),
                u AS (SELECT g, (CASE WHEN CAST(:lat AS double precision) >= 0 THEN 32600 ELSE 32700 END
                                 + LEAST(floor((CAST(:lon AS double precision) + 180) / 6)::int + 1, 60)) AS srid FROM p),
                c AS (SELECT ST_Transform(g, srid) AS m, srid FROM u),
                cell AS (
                  SELECT ST_Transform(
                           ST_Translate(
                             ST_SnapToGrid(ST_Translate(m, -CAST(:grid AS double precision) / 2.0,
                                                           -CAST(:grid AS double precision) / 2.0),
                                           CAST(:grid AS double precision)),
                             CAST(:grid AS double precision) / 2.0, CAST(:grid AS double precision) / 2.0),
                           4326) AS center FROM c)
                SELECT (SELECT ST_Covers(z.geom, (SELECT g FROM p)) FROM geo.zone z WHERE z.zone_id = :zone) AS covered,
                       ST_Y(center) AS glat, ST_X(center) AS glon
                FROM cell
                """
            ),
            {"lat": lat, "lon": lon, "grid": grid_m, "zone": zone_id},
        ).first()
        if row is None or row.covered is None:
            return None
        return Generalized(bool(row.covered), float(row.glat), float(row.glon))

    def add(
        self,
        *,
        zone_id: UUID,
        farmer_id: UUID,
        code: str | None,
        area_ha: Decimal | None,
        center: Generalized,
        grid_m: int,
        created_by: UUID,
    ) -> Parcel:
        parcel = Parcel(
            zone_id=zone_id,
            farmer_id=farmer_id,
            code=code,
            area_ha=area_ha,
            display_grid_m=grid_m,
            created_by=created_by,
            display_geom=None,
        )
        self.s.add(parcel)
        self.s.flush()
        self.s.execute(
            text(
                "UPDATE farm.parcel SET display_geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                "WHERE parcel_id = :p"
            ),
            {"lon": center.lon, "lat": center.lat, "p": parcel.parcel_id},
        )
        self.s.refresh(parcel)
        return parcel

    def get(self, parcel_id: UUID) -> Parcel | None:
        return self.s.get(Parcel, parcel_id)  # RLS: None si no es visible para el usuario

    def display_location(self, parcel_id: UUID) -> tuple[float, float] | None:
        row = self.s.execute(
            text(
                "SELECT round(ST_Y(display_geom)::numeric, 3), round(ST_X(display_geom)::numeric, 3) "
                "FROM farm.parcel WHERE parcel_id = :p AND display_geom IS NOT NULL"
            ),
            {"p": parcel_id},
        ).first()
        return (float(row[0]), float(row[1])) if row else None


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def upsert(
        self,
        parcel_id: UUID,
        weights: dict[str, Decimal],
        constraints: dict[str, Any],
    ) -> PriorityProfile:
        values = {"parcel_id": parcel_id, **weights, "constraints": constraints}
        insert_stmt = pg_insert(PriorityProfile).values(**values)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["parcel_id"],
            set_={**weights, "constraints": constraints, "updated_at": text("now()")},
        ).returning(PriorityProfile.profile_id)
        profile_id = self.s.execute(stmt).scalar_one()
        self.s.expire_all()
        profile = self.s.get(PriorityProfile, profile_id)
        assert profile is not None  # noqa: S101 - acaba de insertarse bajo RLS permitido
        return profile


class SoilRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def properties(self) -> dict[str, SoilProperty]:
        return {p.code: p for p in self.s.scalars(select(SoilProperty))}

    def status_rows(self, parcel_id: UUID) -> list[dict[str, Any]]:
        rows = self.s.execute(
            text(
                """
                SELECT ps.property_code, ps.status::text AS status, sp.max_age_years, sp.unit,
                       lm.value AS m_value, lm.method, lm.depth_from_cm, lm.depth_to_cm, lm.sampled_at,
                       lm.representativeness, lm.ip_id AS m_ip,
                       d.value AS d_value, d.unit AS d_unit, d.ip_id AS d_ip, d.basis
                FROM soil.property_status ps
                JOIN ref.soil_property sp ON sp.code = ps.property_code
                LEFT JOIN LATERAL (
                  SELECT m.value, m.method, s.depth_from_cm, s.depth_to_cm, s.sampled_at,
                         m.representativeness, m.ip_id
                  FROM soil.measurement m JOIN soil.sample s USING (sample_id)
                  WHERE s.parcel_id = ps.parcel_id AND m.property_code = ps.property_code
                  ORDER BY s.sampled_at DESC LIMIT 1) lm ON true
                LEFT JOIN soil.declaration d
                  ON d.parcel_id = ps.parcel_id AND d.property_code = ps.property_code
                WHERE ps.parcel_id = :p ORDER BY ps.property_code
                """
            ),
            {"p": parcel_id},
        ).mappings()
        return [dict(r) for r in rows]

    def insert_provenance(
        self, rec: EvidenceRecord, *, kind: str, indicator_code: str, unit: str
    ) -> UUID:
        ip = IndicatorProvenance(
            indicator_code=indicator_code,
            unit=unit,
            provenance=Provenance(kind),
            evidence_level=Evidence(rec.evidence_level),
            source_ids=rec.source_ids,
            dataset_version=rec.dataset_version,
            processing_method=rec.processing_method,
            assumptions=rec.assumptions,
            limitations=rec.limitations,
            evidence_rule_id=rec.evidence_rule_id,
        )
        self.s.add(ip)
        self.s.flush()
        return ip.ip_id

    def add_sample(
        self,
        parcel_id: UUID,
        sampled_at: date,
        lab: str | None,
        depth_from: int,
        depth_to: int,
    ) -> UUID:
        sample = SoilSample(
            parcel_id=parcel_id,
            sampled_at=sampled_at,
            lab=lab,
            depth_from_cm=depth_from,
            depth_to_cm=depth_to,
        )
        self.s.add(sample)
        self.s.flush()
        return sample.sample_id

    def add_measurement(
        self,
        sample_id: UUID,
        code: str,
        value: float,
        unit: str,
        method: str,
        representativeness: str,
        ip_id: UUID,
    ) -> None:
        self.s.add(
            SoilMeasurement(
                sample_id=sample_id,
                property_code=code,
                value=value,
                unit=unit,
                method=method,
                representativeness=representativeness,
                ip_id=ip_id,
            )
        )
        self.s.flush()

    def upsert_declaration(
        self,
        *,
        parcel_id: UUID,
        code: str,
        value: float,
        unit: str,
        basis: str,
        declared_by: UUID,
        ip_id: UUID,
    ) -> SoilDeclaration:
        existing = self.s.get(SoilDeclaration, (parcel_id, code))
        if existing is not None:
            existing.value, existing.unit, existing.basis = value, unit, basis
            existing.declared_by, existing.ip_id = declared_by, ip_id
            self.s.execute(
                text(
                    "UPDATE soil.declaration SET declared_at = now() WHERE parcel_id=:p AND property_code=:c"
                ),
                {"p": parcel_id, "c": code},
            )
            self.s.flush()
            self.s.refresh(existing)
            return existing
        row = SoilDeclaration(
            parcel_id=parcel_id,
            property_code=code,
            value=value,
            unit=unit,
            basis=basis,
            declared_by=declared_by,
            ip_id=ip_id,
        )
        self.s.add(row)
        self.s.flush()
        self.s.refresh(row)
        return row
