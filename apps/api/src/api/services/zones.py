"""Zonas (contexto climático, dato público) y calidad de datos (lee Parquet curado de R1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from api.errors import NotFound, ValidationFailed
from api.models.enums import JobKind, UserRole
from api.models.farm import Zone
from api.pagination import clamp_limit, decode_cursor, encode_cursor
from api.repositories.farms import ZoneRepository
from api.schemas.common import Page
from api.schemas.runs import SourceOut
from api.schemas.zones import (
    AgriContextOut,
    CoverageRow,
    DataQualityOut,
    DatasetInfo,
    SoilEstimateAvailability,
    SourceComparison,
    ZoneCellOut,
    ZoneCreate,
    ZoneDetail,
    ZoneOut,
)
from api.services.context import ServiceContext
from api.services.jobs import JobService
from api.storage.object_store import ObjectStore
from api.storage.parquet import (
    _ZONE_RE,
    COVERAGE_CONTRACT,
    ParquetDatasetReader,
    curated_path,
)

MAX_JSON_BYTES = 1024 * 1024
PILOT_DEM_META = Path(__file__).resolve().parents[4] / "regions/r2/copernicus_dem_jocotan.json"


def _pilot_dem_elevation(name: str) -> float | None:
    """Fallback documentado para el punto de referencia del piloto si la BD aún no tiene DEM."""
    if name.casefold() != "camotan_jocotan" or not PILOT_DEM_META.is_file():
        return None
    try:
        metadata = json.loads(PILOT_DEM_META.read_text(encoding="utf-8"))
        return float(metadata["reference_samples"]["jocotan_reference"]["elevation_m"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def zone_out(z: Zone) -> ZoneOut:
    elevation = z.elevation_m
    if elevation is None:
        elevation = _pilot_dem_elevation(z.name)
    return ZoneOut(
        zone_id=z.zone_id,
        region_id=z.region_id,
        name=z.name,
        elevation_m=elevation,
        slope_pct=z.slope_pct,
        ready_at=z.ready_at,
    )


def curated_slug(store: ObjectStore, zone: Zone) -> str:
    return curated_slug_for(store, zone.name, zone.zone_id)


def curated_slug_for(store: ObjectStore, name: str, zone_id: UUID) -> str:
    """Directorio de ``curated/`` de la zona: su nombre (convención de R1) o, si no, su UUID.

    R1 escribe ``data/curated/<zona>/`` con el código de zona como nombre en ``geo.zone``. Si existen
    ambos, gana el nombre; si no existe ninguno se informa la ruta por nombre (o UUID si el nombre no
    es un identificador de archivo válido).
    """
    candidates = ([name] if _ZONE_RE.match(name) else []) + [str(zone_id)]
    for c in candidates:
        if store.exists(curated_path(c, "coverage")):
            return c
    return candidates[0]


def read_json(store: ObjectStore, relative: str) -> dict[str, Any]:
    """JSON auxiliar de R1 (``curated_meta``, validaciones). Ausente o ilegible ⇒ vacío, sin inventar."""
    if not store.exists(relative) or store.size(relative) > MAX_JSON_BYTES:
        return {}
    try:
        with store.open_read(relative) as fh:
            data = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def comparisons_from_r1(validation: dict[str, Any]) -> list[SourceComparison]:
    """``precip_validation.json`` de R1 -> comparaciones entre productos (no son validación local)."""
    pv = validation.get("IMERG_vs_POWER")
    if not isinstance(pv, dict):
        return []
    n = pv.get("n_days_compared")
    annual = {
        str(y): float(v["ratio"])
        for y, v in (pv.get("annual_totals_mm") or {}).items()
        if isinstance(v, dict) and _num(v.get("ratio")) is not None
    }
    return [
        SourceComparison(
            pair="IMERG_FINAL_V07 vs POWER_DAILY",
            n_days_common=n if isinstance(n, int) and not isinstance(n, bool) else None,
            bias_mm_day=_num(pv.get("bias_mm_day_imerg_minus_power")),
            correlation_daily=_num(pv.get("corr_daily")),
            correlation_dekad=_num(pv.get("corr_dekad_sum")),
            ratio_total=_num(pv.get("ratio_total_imerg_over_power")),
            annual_ratio=annual,
            note=str(pv["note"])[:500] if pv.get("note") else None,
        )
    ]


class ZoneService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.repo = ZoneRepository(ctx.session)

    def list(self, cursor: str | None, limit: int | None) -> Page[ZoneOut]:
        n = clamp_limit(limit, self.ctx.settings)
        raw = decode_cursor(cursor)
        after = None
        if raw is not None:
            try:
                after = (str(raw[0]), UUID(str(raw[1])))
            except (IndexError, ValueError) as exc:
                raise ValidationFailed("Cursor no válido") from exc
        rows = self.repo.page(after, n)
        page, more = rows[:n], len(rows) > n
        nxt = encode_cursor([page[-1].name, str(page[-1].zone_id)]) if more and page else None
        return Page[ZoneOut](items=[zone_out(z) for z in page], next_cursor=nxt)

    def get(self, zone_id: UUID) -> ZoneDetail:
        zone = self.repo.get(zone_id)
        if zone is None:
            raise NotFound("Zona no encontrada")
        base = zone_out(zone).model_dump()
        cells = self.repo.cells(zone_id)
        slug = curated_slug(self.ctx.store, zone)
        meta = read_json(self.ctx.store, f"curated/{slug}/curated_meta.json")
        codes = sorted({c["source"] for c in cells} | self._meta_source_codes(meta))
        from api.adapters.agri_context import agri_context

        context = agri_context(self.ctx.settings)
        return ZoneDetail(
            **base,
            cells=[ZoneCellOut(**c) for c in cells],
            sources=[SourceOut(**s) for s in self.repo.sources_by_codes(codes)],
            geometry=self.repo.geojson(zone_id),
            soil_estimates=[
                SoilEstimateAvailability(**e) for e in self.repo.soil_estimates(zone_id)
            ],
            agri_context=AgriContextOut(**context) if context else None,
        )

    def create(self, body: ZoneCreate, idempotency_key: str | None) -> tuple[object, bool]:
        self.ctx.user.require_role(UserRole.tecnico, UserRole.admin)
        jobs = JobService(self.ctx)
        previous = jobs.existing(JobKind.zone_ingest, idempotency_key)
        if previous is not None:  # reintento idempotente: no se crea otra zona
            return previous, False
        zone_id = self.repo.create(body.region_id, body.name, body.geometry)
        if zone_id is None:
            self.ctx.uow.rollback()
            raise ValidationFailed(
                "La región no existe o la geometría no es válida / no está dentro de la región"
            )
        # Zona + trabajo en la misma transacción lógica: si el trabajo es un duplicado idempotente,
        # JobService revierte y la zona nueva no se conserva.
        return jobs.submit(JobKind.zone_ingest, {"zone_id": str(zone_id)}, idempotency_key)

    @staticmethod
    def _meta_source_codes(meta: dict[str, Any]) -> set[str]:
        return _meta_source_codes_impl(meta)

    def data_quality(
        self,
        zone_id: UUID,
        variable: str | None,
        year: int | None,
        cursor: str | None,
        limit: int | None,
    ) -> DataQualityOut:
        zone = self.repo.get(zone_id)
        if zone is None:
            raise NotFound("Zona no encontrada")
        slug = curated_slug(self.ctx.store, zone)
        rel = curated_path(slug, "coverage")
        reader = ParquetDatasetReader(self.ctx.store)
        df = reader.read(rel, COVERAGE_CONTRACT)  # 503 DATASET_UNAVAILABLE / DATASET_INCOMPATIBLE
        sha = self.ctx.store.sha256(rel)
        total = len(df)
        if variable is not None:
            df = df[df["variable"] == variable]
        if year is not None:
            df = df[df["year"] == year]
        order = (["cell_id"] if "cell_id" in df.columns else []) + list(COVERAGE_CONTRACT.key)
        df = df.sort_values(order, kind="mergesort")
        n = clamp_limit(limit, self.ctx.settings)
        raw = decode_cursor(cursor)
        start = int(raw[0]) if raw else 0
        chunk = df.iloc[start : start + n]
        nxt = encode_cursor([start + n]) if start + n < len(df) else None
        cols = [
            c
            for c in ("cell_id", "variable", "year", "n_expected", "n_valid", "pct_missing")
            if c in df.columns
        ]
        rows = [
            CoverageRow(**{str(k): (None if _isnan(v) else v) for k, v in rec.items()})
            for rec in chunk[cols].to_dict("records")
        ]
        meta = read_json(self.ctx.store, f"curated/{slug}/curated_meta.json")
        # `precip_validation.json` es la comparación IMERG/POWER que declara el README de R1; la
        # sensibilidad de `ea` (T2MDEW vs RH2M) sale de `validation_report.json`.
        validation = read_json(self.ctx.store, f"curated/{slug}/precip_validation.json")
        report = read_json(self.ctx.store, f"curated/{slug}/validation_report.json")
        ea = (report.get("et0_T2MDEW_vs_RH2M") or {}).get("mean_abs_diff_mm_day")
        limitations = [str(x)[:500] for x in (meta.get("limitations") or []) if isinstance(x, str)]
        return DataQualityOut(
            zone_id=zone_id,
            sources=[
                SourceOut(**s)
                for s in self.repo.sources_by_codes(sorted(self._meta_source_codes(meta)))
            ],
            comparisons=comparisons_from_r1(validation),
            ea_sensitivity_mm_day=_num(ea),
            limitations=limitations,
            dataset=DatasetInfo(
                relative_path=rel,
                sha256=sha,
                n_rows=total,
                contract_status=COVERAGE_CONTRACT.status,
            ),
            coverage=rows,
            next_cursor=nxt,
        )


def _meta_source_codes_impl(meta: dict[str, Any]) -> set[str]:
    return {str(meta[k]) for k in ("precip_primary", "precip_fallback") if meta.get(k)}


def _isnan(v: object) -> bool:
    return isinstance(v, float) and v != v  # noqa: PLR0124 - NaN != NaN
