"""Corridas y endpoints de análisis (BE-06).

R3 coordina, autoriza y transporta: NO calcula. Las lecturas pasan por ``EnginePort``; si el motor
(R2) no está integrado el resultado es 503 DEPENDENCY_NOT_INTEGRATED, nunca un dato simulado.
Un escenario no calculado devuelve 409 SCENARIO_NOT_COMPUTED (con enlace al trabajo que lo calcula)
y NUNCA se calcula en silencio dentro de una petición de lectura (README §16).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from api.adapters.errors import translate_engine_error
from api.adapters.ports import RunRef
from api.contracts.provisional_enums import Label
from api.errors import ApiError, Conflict, ErrorCode, NotFound
from api.models.engine import AnalysisRun
from api.models.enums import ConsentPurpose, JobKind, UserRole
from api.repositories.analysis import ProvenanceRepository, RunRepository
from api.repositories.farms import ZoneRepository
from api.schemas.runs import (
    PeriodOut,
    ProvenanceOut,
    RankRequest,
    RunCreate,
    RunOut,
    ScenariosCreate,
    ScenarioTag,
    SoilVoiRequest,
    SourceOut,
)
from api.services.access import AccessPolicy
from api.services.context import ServiceContext
from api.services.jobs import JobService


def _flag(params: Mapping[str, Any], key: str) -> bool | None:
    value = params.get(key)
    return value if isinstance(value, bool) else None


MODE_LABEL = {
    "exposure": Label.indicador_exposicion_climatica,
    "root_zone": Label.balance_hidrico_zona_radicular,
}


def run_ref_from_db(session: Session, run_id: UUID) -> RunRef:
    run = RunRepository(session).get(run_id)
    if run is None:
        raise NotFound("Corrida no encontrada")
    return RunRef(
        run_id=run.run_id,
        zone_id=run.zone_id,
        parcel_id=run.parcel_id,
        data_hash=run.data_hash,
        params_hash=run.params_hash,
        region_config_hash=run.region_config_hash,
        code_version=run.code_version,
        seed=run.seed,
    )


class ScenarioNotComputed(Conflict):
    code = ErrorCode.SCENARIO_NOT_COMPUTED
    title = "Escenario no calculado"


class RunNotReady(Conflict):
    code = ErrorCode.RUN_NOT_READY
    title = "La corrida aún no está lista"


def etag_for(run: AnalysisRun, endpoint: str, params: Mapping[str, Any]) -> str:
    """ETag por (run_id, endpoint, parámetros); cambia si cambian los hashes de la corrida."""
    material = "|".join(
        [
            str(run.run_id),
            endpoint,
            run.data_hash,
            run.params_hash,
            run.region_config_hash,
            run.status,
            repr(sorted(params.items())),
        ]
    )
    return '"' + hashlib.sha256(material.encode()).hexdigest()[:32] + '"'


class RunService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.runs = RunRepository(ctx.session)
        self.access = AccessPolicy(ctx)

    # -- acceso -------------------------------------------------------------------------------
    def visible_run(self, run_id: UUID) -> AnalysisRun:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFound("Corrida no encontrada")
        if run.parcel_id is not None:
            self.access.parcel(self.ctx.user, run.parcel_id)  # 404 si no accede a la parcela
        elif self.ctx.user.role == UserRole.agricultor:
            pass  # corridas de zona: contexto público para usuarios autenticados
        return run

    def _ref(self, run: AnalysisRun) -> RunRef:
        return RunRef(
            run.run_id,
            run.zone_id,
            run.parcel_id,
            run.data_hash,
            run.params_hash,
            run.region_config_hash,
            run.code_version,
            run.seed,
        )

    def _ready(self, run: AnalysisRun) -> None:
        if run.status != "ok":
            raise RunNotReady(f"La corrida está en estado '{run.status}'")

    def _require_computed(self, run: AnalysisRun, scenario_id: str, adaptation: str) -> None:
        sr = self.runs.scenario(run.run_id, scenario_id, adaptation)
        if sr is None or sr.status != "ok":
            raise ScenarioNotComputed(
                "El escenario/lectura solicitado no ha sido calculado para esta corrida",
                hint=f"Solicite el cálculo con POST /v1/runs/{run.run_id}/scenarios (trabajo asíncrono).",
            )

    # -- escritura (trabajos) ------------------------------------------------------------------
    def create_base_run(self, zone_id: UUID, body: RunCreate, key: str | None) -> tuple[Any, bool]:
        self.ctx.user.require_role(UserRole.tecnico, UserRole.admin)
        if ZoneRepository(self.ctx.session).get(zone_id) is None:
            raise NotFound("Zona no encontrada")
        if body.parcel_id is not None:
            parcel = self.access.parcel(self.ctx.user, body.parcel_id)
            self.access.require_consent_for_parcel(parcel, ConsentPurpose.analysis)
        payload = {"zone_id": str(zone_id), **body.model_dump(mode="json")}
        return JobService(self.ctx).submit(JobKind.analysis_run, payload, key)

    def create_scenarios(
        self, run_id: UUID, body: ScenariosCreate, key: str | None
    ) -> tuple[Any, bool]:
        self.ctx.user.require_role(UserRole.tecnico, UserRole.admin)
        run = self.visible_run(run_id)
        self._ready(run)
        payload = {"run_id": str(run_id), **body.model_dump(mode="json")}
        return JobService(self.ctx).submit(JobKind.scenario_run, payload, key)

    # -- lecturas -------------------------------------------------------------------------------
    def get(self, run_id: UUID) -> AnalysisRun:
        return self.visible_run(run_id)

    def to_out(self, run: AnalysisRun) -> RunOut:
        params = run.params if isinstance(run.params, dict) else {}
        return RunOut(
            label=MODE_LABEL.get(str(run.mode)),
            catalog_hash=self.runs.catalog_hash(run.catalog_release_id),
            sandbox=_flag(params, "sandbox"),
            synthetic_fixture=_flag(params, "synthetic_fixture"),
            run_id=run.run_id,
            zone_id=run.zone_id,
            parcel_id=run.parcel_id,
            period_start=run.period_start,
            period_end=run.period_end,
            mode=run.mode,
            mode_reasons=list(run.mode_reasons or []),
            status=run.status,
            params_hash=run.params_hash,
            region_config_hash=run.region_config_hash,
            catalog_release_id=run.catalog_release_id,
            data_hash=run.data_hash,
            code_version=run.code_version,
            seed=run.seed,
            created_at=run.created_at,
        )

    def scenarios(self, run_id: UUID) -> list[ScenarioTag]:
        self.visible_run(run_id)
        return [ScenarioTag(**row) for row in self.runs.scenario_tags(run_id)]

    @staticmethod
    def _call(fn: Callable[[], Mapping[str, Any]]) -> Mapping[str, Any]:
        """Invoca el motor y traduce sus errores de dominio tipados a códigos de la API."""
        try:
            return fn()
        except ApiError:
            raise
        except Exception as exc:
            translated = translate_engine_error(exc)
            if translated is None:
                raise
            raise translated from exc

    def present(self, kind: str, run_id: UUID, params: dict[str, Any]) -> Mapping[str, Any]:
        """summary | heatmap | dekad_chart | climate_history vía EnginePort (R2)."""
        run = self.visible_run(run_id)
        self._ready(run)
        scenario = params.get("scenario")
        if kind != "climate_history" and scenario is not None:
            self._require_computed(run, str(scenario), str(params.get("adaptation", "none")))
        method = getattr(self.ctx.ports.engine, kind)
        return self._call(lambda: method(self._ref(run), params))

    def rank(self, run_id: UUID, body: RankRequest) -> Mapping[str, Any]:
        run = self.visible_run(run_id)
        self._ready(run)
        self._require_computed(run, body.scenario_id, body.adaptation_mode.value)
        payload = body.model_dump(mode="json")
        return self._call(lambda: self.ctx.ports.engine.rank(self._ref(run), payload))

    def soil_voi(self, run_id: UUID, body: SoilVoiRequest | None) -> Mapping[str, Any]:
        body = body or SoilVoiRequest()
        run = self.visible_run(run_id)
        if run.parcel_id is None:
            raise NotFound("La corrida no está asociada a una parcela")
        self.access.parcel(self.ctx.user, run.parcel_id, owner_only=False)
        self._ready(run)
        self._require_computed(run, body.scenario_id, body.adaptation_mode.value)
        payload = body.model_dump(mode="json")
        return self._call(lambda: self.ctx.ports.engine.soil_voi(self._ref(run), payload))


def iso_duration(value: timedelta | None) -> str | None:
    """Duración ISO 8601 (``P1D``, ``PT6H``) de un ``interval`` de PostgreSQL."""
    if value is None:
        return None
    hours, rest = divmod(value.seconds, 3600)
    minutes, secs = divmod(rest, 60)
    clock = "".join(f"{n}{u}" for n, u in ((hours, "H"), (minutes, "M"), (secs, "S")) if n)
    body = (f"{value.days}D" if value.days else "") + (f"T{clock}" if clock else "")
    return f"P{body}" if body else "PT0S"


class ProvenanceService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.repo = ProvenanceRepository(ctx.session)

    def get(self, ip_id: UUID) -> ProvenanceOut:
        d = self.repo.get_detail(ip_id)
        if d is None:
            raise NotFound("Procedencia no encontrada")
        period = (
            PeriodOut(start=d["period_start"], end=d["period_end"])
            if d["period_start"] or d["period_end"]
            else None
        )
        return ProvenanceOut(
            ip_id=d["ip_id"],
            run_id=d["run_id"],
            indicator_code=d["indicator_code"],
            unit=d["unit"],
            provenance=d["provenance"],
            evidence=d["evidence_level"],
            evidence_rule=d["evidence_rule_id"],
            sources=[SourceOut(**s) for s in d["sources"]],
            dataset_version=d["dataset_version"],
            period=period,
            spatial_res=f"{d['spatial_res_m']} m" if d["spatial_res_m"] is not None else None,
            temporal_res=iso_duration(d["temporal_res"]),
            method=d["processing_method"],
            retrieved_at=d["retrieved_at"],
            missing_pct=d["missing_pct"],
            assumptions=list(d["assumptions"] or []),
            limitations=list(d["limitations"] or []),
        )


__all__ = [
    "ApiError",
    "ProvenanceService",
    "RunNotReady",
    "RunService",
    "ScenarioNotComputed",
    "etag_for",
    "run_ref_from_db",
]
