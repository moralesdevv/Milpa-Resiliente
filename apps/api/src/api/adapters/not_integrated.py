"""Implementaciones por defecto: dependencia pendiente. Nunca devuelven datos."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from uuid import UUID

from api.adapters.ports import EvidenceRecord, Ports, RunRef
from api.errors import DependencyNotIntegrated

R2 = "R2 (packages/milpa_core)"
R1 = "R1 (milpa_etl / datos curados)"


class NotIntegratedEngine:
    component = R2

    def is_available(self) -> bool:
        return False

    def _fail(self, what: str) -> DependencyNotIntegrated:
        return DependencyNotIntegrated(self.component, what)

    def run_base_analysis(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("La corrida base (run_analysis)")

    def run_scenarios(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("La ejecución de escenarios")

    def rank(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El ranking multicriterio (rank / rank_stability)")

    def soil_voi(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("Soil VoI (soil_voi)")

    def build_report(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El modelo de informe (build_report)")

    def summary(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El resumen de riesgo (StrategyRiskDTO)")

    def heatmap(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El heatmap (HeatmapDTO)")

    def dekad_chart(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El gráfico por decena (DekadChartDTO)")

    def climate_history(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._fail("El historial climático")


class NotIntegratedEvidence:
    component = "R2 (milpa_core.provenance: reglas de evidencia A/B/C)"

    def is_available(self) -> bool:
        return False

    def provenance_for_soil(
        self,
        *,
        kind: Literal["medido", "declarado"],
        property_code: str,
        unit: str,
        method: str | None,
        representativeness: str | None,
    ) -> EvidenceRecord:
        raise DependencyNotIntegrated(
            self.component, "La asignación de nivel de evidencia (A/B/C) para suelo"
        )


class NotIntegratedIngest:
    component = R1

    def is_available(self) -> bool:
        return False

    def ingest_zone(self, zone_id: UUID) -> Mapping[str, Any]:
        raise DependencyNotIntegrated(self.component, "La ingesta y curación de la zona")


def default_ports() -> Ports:
    return Ports(
        engine=NotIntegratedEngine(),
        evidence=NotIntegratedEvidence(),
        ingest=NotIntegratedIngest(),
    )
