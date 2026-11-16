"""Adaptador hacia ``milpa_core`` (R2). ESTADO: ``adapter_ready`` — NO integrado ni verificado.

R3 no copia ni reimplementa el motor. Este módulo:
  * importa ``milpa_core`` de forma perezosa (el paquete aún no existe);
  * verifica que la fachada pública coincida con la firma documentada (README §10);
  * deja explícito lo que falta: el ensamblado de ``RunContext`` y los constructores de los DTO de
    presentación (summary/heatmap/dekad/historial), cuya firma R2 no ha publicado.

Cuando R2 entregue el paquete: ``python -m api.cli check-core`` informa discrepancias de firma y
solo entonces se completan los métodos marcados ``PENDING_R2`` (ADR-009).
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from api.adapters.ports import RunRef
from api.errors import DependencyNotIntegrated

# Parámetros posicionales documentados en README §10 ("Fachada pública").
DOCUMENTED_FACADE: dict[str, tuple[str, ...]] = {
    "run_analysis": ("ctx", "scenario", "adaptation"),
    "rank": ("ctx", "results", "weights", "cfg"),
    "rank_stability": ("ctx", "inputs", "cfg"),
    "soil_voi": ("ctx", "parcel", "strategies", "cfg"),
    "build_report": ("ctx", "bundle", "locale"),
}


@dataclass(frozen=True)
class ContractReport:
    package_present: bool
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.package_present and not self.problems


def import_core() -> ModuleType | None:
    try:
        return importlib.import_module("milpa_core")
    except ModuleNotFoundError as exc:
        if exc.name == "milpa_core":
            return None
        raise


def check_core_contract(core: ModuleType | None = None) -> ContractReport:
    core = core if core is not None else import_core()
    if core is None:
        return ContractReport(False, ("paquete milpa_core no instalado (pendiente de R2)",))
    problems: list[str] = []
    for name, expected in DOCUMENTED_FACADE.items():
        fn = getattr(core, name, None)
        if not callable(fn):
            problems.append(f"falta la función pública {name}")
            continue
        params = tuple(inspect.signature(fn).parameters)[: len(expected)]
        if params != expected:
            problems.append(f"{name}: parámetros {params} != documentados {expected}")
    return ContractReport(True, tuple(problems))


class MilpaCoreEngine:
    """Delegación 1:1 a la fachada. Los métodos PENDING_R2 fallan de forma explícita."""

    component = "R2 (packages/milpa_core)"

    def __init__(self, core: ModuleType) -> None:
        report = check_core_contract(core)
        if not report.ok:
            raise RuntimeError(
                "milpa_core no cumple la fachada documentada: " + "; ".join(report.problems)
            )
        self._core = core

    def is_available(self) -> bool:
        return True

    def _pending(self, what: str, why: str) -> DependencyNotIntegrated:
        return DependencyNotIntegrated(self.component, f"{what} (PENDING_R2: {why})")

    def run_base_analysis(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending(
            "run_analysis", "ensamblado de RunContext desde datos curados R1 no definido"
        )

    def run_scenarios(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("run_analysis por escenario", "ensamblado de RunContext no definido")

    def rank(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending(
            "rank/rank_stability", "mapeo de resultados persistidos a StrategyRisk no definido"
        )

    def soil_voi(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("soil_voi", "construcción de SoilContext no definida")

    def build_report(self, run: RunRef, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("build_report", "AnalysisBundle no definido")

    def summary(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("summary", "R2 no publicó función para construir StrategyRiskDTO")

    def heatmap(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("heatmap", "R2 no publicó función para construir HeatmapDTO")

    def dekad_chart(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("dekad-chart", "R2 no publicó función para construir DekadChartDTO")

    def climate_history(self, run: RunRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._pending("climate-history", "contrato del historial climático no definido")
