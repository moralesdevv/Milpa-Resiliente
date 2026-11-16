"""DOBLES DE PRUEBA (test doubles). NO son implementaciones de R1/R2 ni simulan ciencia.

Existen solo para ejercitar rutas de R3 que dependen de puertos aún no integrados (p. ej. guardar
mediciones exige una regla de evidencia que decide R2). Toda salida lleva la marca ``test-double``.
Jamás deben importarse desde ``src/api``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from api.adapters.not_integrated import NotIntegratedEngine
from api.adapters.ports import EvidenceRecord, RunRef


class FakeEvidence:
    component = "TEST DOUBLE (no es R2)"

    def is_available(self) -> bool:
        return True

    def provenance_for_soil(
        self,
        *,
        kind: Literal["medido", "declarado"],
        property_code: str,
        unit: str,
        method: str | None,
        representativeness: str | None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_level="C",
            evidence_rule_id="TEST-DOUBLE-RULE",
            processing_method=f"test-double:{kind}:{property_code}",
            assumptions=["valor de prueba"],
            limitations=["no usar fuera de pruebas"],
        )


class FakeEngine(NotIntegratedEngine):
    """Motor de prueba: registra las llamadas y devuelve un payload marcado como doble."""

    component = "TEST DOUBLE (no es R2)"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def is_available(self) -> bool:
        return True

    def _rec(self, name: str, req: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((name, dict(req)))
        return {"test_double": True, "method": name}

    def rank(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("rank", request)

    def soil_voi(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("soil_voi", request)

    def summary(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("summary", params)

    def heatmap(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("heatmap", params)

    def dekad_chart(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("dekad_chart", params)

    def climate_history(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._rec("climate_history", params)
