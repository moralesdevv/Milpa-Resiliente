"""milpa_core — núcleo científico de MILPA RESILIENTE 3.3 (rol R2).

Librería pura: no lee archivos, no abre conexiones, no conoce FastAPI.
Fachada estable: ``run_analysis``, ``rank``, ``rank_stability``, ``soil_voi``, ``build_report``.
"""
from .facade import (
    ENGINE_VERSION,
    RunContext,
    ScenarioRunResult,
    make_context,
    rank,
    rank_stability,
    run_analysis,
    run_grid,
    soil_voi,
)
from .report_model import build_report
from .scenarios import BASE, ScenarioDef, standard_grid

__version__ = "0.1.0"
__all__ = [
    "ENGINE_VERSION", "RunContext", "ScenarioRunResult", "make_context", "rank", "rank_stability", "run_analysis",
    "run_grid", "soil_voi", "build_report", "BASE", "ScenarioDef", "standard_grid",
]
