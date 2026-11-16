"""Configuración tipada que entra por parámetro (sin estado global).

Los valores por defecto marcados [Pendiente] son propuestas de sandbox; el region
pack los sobrescribe. En producción, ``RegionConfig.validate_production`` falla si
alguno sigue en None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from .enums import Criterion, PeffMethod


@dataclass(frozen=True)
class Season:
    code: str
    calendar_year_shift: int
    plant_window: tuple[str, str]  # MM-DD, MM-DD


@dataclass(frozen=True)
class OnsetDef:
    """Inicio de lluvias: desde search_start, acumulado ≥ x_mm en n_days y sin racha seca
    > y_days (día seco < dry_day_mm) en los z_days siguientes. Parámetros con cita [Pendiente]."""

    search_start_md: str
    x_mm: float
    n_days: int
    y_days: int
    z_days: int
    dry_day_mm: float = 1.0
    citation: str | None = None


@dataclass(frozen=True)
class RegionConfig:
    code: str
    status: Literal["sandbox", "production"]
    lat_deg: float
    elevation_m: float
    window_start: str  # YYYY-MM-DD
    window_end: str
    seasons: Mapping[str, Season]
    agri_year_start: str = "04-01"  # [Pendiente]
    min_valid_years: int = 3  # [Pendiente]
    step_days: int = 5  # [Pendiente]
    primary_peff: PeffMethod = PeffMethod.USDA_SCS_FAO
    peff_enabled: tuple[PeffMethod, ...] = (PeffMethod.USDA_SCS_FAO, PeffMethod.FAO_DEPENDABLE, PeffMethod.UPPER_BOUND)
    phi: float | None = None  # fixed_fraction [Pendiente]
    max_missing_precip_pct: float = 0.0  # [Pendiente] — por defecto estricto: ninguna lluvia faltante
    max_missing_met_pct: float = 10.0  # [Pendiente]
    ea_sensitivity_tol_pct: float | None = 5.0  # [Pendiente]
    onset: OnsetDef | None = None
    adaptation_lag_days: int | None = None
    adaptation_citation: str | None = None
    buffer_days: int = 30
    min_segment_days: int = 1  # segmentos decena∩etapa más cortos no se comparan con el umbral [Propuesto R2]
    priorities_default: Mapping[Criterion, float] = field(default_factory=lambda: {c: 0.25 for c in Criterion})
    accepted_awc_ptf: tuple[str, ...] = ()
    communication_tol_pct: float = 10.0  # tolerancia de comunicación (cambio "notable") [Pendiente]

    @property
    def start_year(self) -> int:
        return int(self.window_start[:4])

    @property
    def end_year(self) -> int:
        return int(self.window_end[:4])

    def pending_fields(self) -> list[str]:
        out = []
        if self.onset is None or not self.onset.citation:
            out.append("onset")
        if self.adaptation_lag_days is None or not self.adaptation_citation:
            out.append("adaptation")
        if PeffMethod.FIXED_FRACTION in self.peff_enabled and self.phi is None:
            out.append("phi")
        return out

    @property
    def delay_scenarios_enabled(self) -> bool:
        if self.onset is None:
            return False
        return self.status == "sandbox" or bool(self.onset.citation)

    @property
    def onset_rule_enabled(self) -> bool:
        if not self.delay_scenarios_enabled or self.adaptation_lag_days is None:
            return False
        return self.status == "sandbox" or bool(self.adaptation_citation)


@dataclass(frozen=True)
class RiskConfig:
    min_valid_years: int = 3
    eps: float = 1e-6
    consistent_window_min_dates: int = 3


@dataclass(frozen=True)
class RankingConfig:
    min_weight_coverage: float = 0.5  # [Pendiente] de consenso
    missing_policy: Literal["common_support", "exclude_incomplete"] = "common_support"
    reference_scales: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    tie_eps: float = 1e-9
    n_boot: int = 500
    seed: int = 0


@dataclass(frozen=True)
class StabilityConfig:
    n_samples: int = 2000
    mode: Literal["dirichlet", "ball"] = "dirichlet"
    concentration: float = 50.0
    radius: float = 0.10
    stable_share: float = 0.80  # umbral de comunicación, no estadístico [Pendiente]
    unstable_share: float = 0.50  # umbral de comunicación, no estadístico [Pendiente]
    min_samples: int = 500
    seed: int = 0


@dataclass(frozen=True)
class VoiConfig:
    n_hyp: int = 5
    top_k: int = 3
    zone_ph_range: tuple[float, float] | None = None  # rango agronómico citado [Pendiente]
    zone_ph_range_citation: str | None = None


@dataclass(frozen=True)
class SoilCriterionConfig:
    min_subindicator_coverage: float = 0.5  # [Pendiente]
