"""Puertos de integración con R1 y R2 (spec R3 §12).

La API depende de estos Protocols, nunca de implementaciones científicas. Las implementaciones por
defecto (``not_integrated``) fallan con ``DependencyNotIntegrated``: no existen resultados falsos.
Los tipos que cruzan el puerto son ``Mapping[str, Any]`` JSON-serializables porque los DTO
científicos son propiedad de R2 (README §15) y aún no existen; cuando lleguen, el adaptador real los
validará y los volcará con ``model_dump(mode="json")``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class RunRef:
    """Identificación de una corrida ya persistida (sin lógica científica)."""

    run_id: UUID
    zone_id: UUID
    parcel_id: UUID | None
    data_hash: str
    params_hash: str
    region_config_hash: str
    code_version: str
    seed: int


class EnginePort(Protocol):
    """Puerto hacia ``milpa_core`` (R2). Firmas de la fachada: README §10 / R2_ENGINE_CONTRACT.md."""

    component: str

    def is_available(self) -> bool: ...
    def run_base_analysis(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def run_scenarios(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def rank(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def soil_voi(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def build_report(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    # Presentación de resultados: R2 no publica firma en la fachada (hueco registrado).
    def summary(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def heatmap(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def dekad_chart(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def climate_history(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class EvidenceRecord:
    """Procedencia decidida por R2 (reglas A/B/C). R3 solo la persiste."""

    evidence_level: Literal["A", "B", "C"]
    evidence_rule_id: str
    processing_method: str
    source_ids: list[int] = field(default_factory=list)
    dataset_version: str | None = None
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class EvidencePort(Protocol):
    component: str

    def is_available(self) -> bool: ...

    def provenance_for_soil(
        self,
        *,
        kind: Literal["medido", "declarado"],
        property_code: str,
        unit: str,
        method: str | None,
        representativeness: str | None,
    ) -> EvidenceRecord: ...


class IngestPort(Protocol):
    """Disparo/seguimiento de la ingesta de una zona (R1). La API NO importa ``milpa_etl``."""

    component: str

    def is_available(self) -> bool: ...
    def ingest_zone(self, zone_id: UUID) -> Mapping[str, Any]: ...


@dataclass
class Ports:
    engine: EnginePort
    evidence: EvidencePort
    ingest: IngestPort
    extra: dict[str, Any] = field(default_factory=dict)
