"""Catálogo tipado, calendario fenológico (días o grados-día) y curva Kc (apartado 11.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from ..enums import Evidence, Mode, PeffMethod, ThresholdMetric
from ..errors import MixedCycleLengthError


@dataclass(frozen=True)
class Stage:
    code: str
    seq: int
    kc_start: float
    kc_end: float
    critical: bool = False
    length_days: int | None = None
    gdd_start: float | None = None
    gdd_end: float | None = None
    citation: str | None = None
    evidence: Evidence = Evidence.C

    @property
    def cited(self) -> bool:
        return bool(self.citation)


@dataclass(frozen=True)
class Variety:
    code: str
    crop: str
    name: str
    phenology_basis: str  # 'days' | 'gdd'
    stages: tuple[Stage, ...]
    family: str = ""
    gdd_base_c: float | None = None
    z_min_m: float | None = None
    z_max_m: float | None = None
    depletion_fraction_p: float | None = None
    root_citation: str | None = None
    p_citation: str | None = None
    fallow_kc: float | None = None
    fallow_kc_citation: str | None = None
    citation: str | None = None

    def __post_init__(self) -> None:
        if self.phenology_basis not in ("days", "gdd"):
            raise ValueError(f"{self.code}: phenology_basis debe ser days|gdd")
        seqs = [s.seq for s in self.stages]
        if seqs != sorted(seqs):
            raise ValueError(f"{self.code}: etapas fuera de orden")
        if self.phenology_basis == "days" and any(s.length_days is None for s in self.stages):
            raise ValueError(f"{self.code}: etapa sin length_days")
        if self.phenology_basis == "gdd" and (self.gdd_base_c is None or any(s.gdd_end is None for s in self.stages)):
            raise ValueError(f"{self.code}: fenología gdd sin base o sin gdd_end")

    @property
    def cycle_days(self) -> int | None:
        if self.phenology_basis != "days":
            return None
        return int(sum(s.length_days for s in self.stages))

    @property
    def root_depth_cited(self) -> bool:
        return bool(self.root_citation) and self.z_max_m is not None

    @property
    def depletion_fraction_cited(self) -> bool:
        return bool(self.p_citation) and self.depletion_fraction_p is not None

    @property
    def critical_stages(self) -> tuple[Stage, ...]:
        return tuple(s for s in self.stages if s.critical)

    @property
    def kc_evidence(self) -> Evidence:
        return min((s.evidence if s.cited else Evidence.C for s in self.stages), key=lambda e: e.rank)

    @property
    def kc_cited(self) -> bool:
        return all(s.cited for s in self.stages)

    def stage_signature(self) -> tuple:
        return tuple((s.code, s.length_days, s.gdd_end) for s in self.stages)


@dataclass(frozen=True)
class Crop:
    code: str
    name_es: str
    family: str
    is_legume: bool = False
    fixes_n_conditions: str | None = None
    residue_return: float | None = None
    residue_citation: str | None = None


@dataclass(frozen=True)
class Threshold:
    crop: str
    stage: str
    metric: ThresholdMetric
    value: float | None
    sens_low: float | None = None
    sens_high: float | None = None
    peff_method: PeffMethod | None = None
    mode: Mode = Mode.EXPOSURE
    unit: str = "mm"
    evidence: Evidence = Evidence.C
    citation: str | None = None

    @property
    def cited(self) -> bool:
        return bool(self.citation) and self.value is not None

    def at(self, level: str) -> float | None:
        return {"central": self.value, "low": self.sens_low, "high": self.sens_high}[level]


@dataclass(frozen=True)
class PhTolerance:
    crop: str
    ph_abs_min: float
    ph_opt_min: float
    ph_opt_max: float
    ph_abs_max: float
    ph_method: str
    evidence: Evidence
    citation: str


@dataclass(frozen=True)
class Catalogs:
    crops: Mapping[str, Crop]
    varieties: Mapping[str, Variety]
    thresholds: tuple[Threshold, ...] = ()
    ph_tolerance: Mapping[str, PhTolerance] = field(default_factory=dict)
    reference_yields_kg_ha: Mapping[str, tuple[float, Evidence, str]] = field(default_factory=dict)  # variety → (kg/ha, ev, cita)
    food_composition: Mapping[str, tuple[float, float, str]] = field(default_factory=dict)  # crop → (kcal/kg, prot g/kg, cita)
    prices: Mapping[str, tuple[float, str, str, str]] = field(default_factory=dict)  # crop → (precio/kg, moneda, fecha, fuente)
    variable_costs_ha: Mapping[str, tuple[float, str, str, str]] = field(default_factory=dict)
    catalog_hash: str = "sandbox"
    mode: str = "sandbox"  # sandbox | production

    def threshold(self, crop: str, stage: str, peff_method: str | None, mode: Mode = Mode.EXPOSURE) -> Threshold | None:
        """Un umbral definido con un método de Pef solo se usa con ese método."""
        for t in self.thresholds:
            if t.crop == crop and t.stage == stage and t.mode == mode:
                if mode is Mode.EXPOSURE and t.peff_method is not None and peff_method is not None \
                        and PeffMethod(t.peff_method).value != PeffMethod(peff_method).value:
                    continue
                if self.mode == "production" and not t.cited:
                    return None
                return t
        return None


# ------------------------------------------------------------------ calendario

@dataclass(frozen=True)
class Calendar:
    variety: str
    plant_date: np.datetime64
    harvest_date: np.datetime64  # último día del ciclo (incluido)
    stage_idx: np.ndarray  # índice de etapa por día del ciclo
    kc: np.ndarray
    critical: np.ndarray
    stage_codes: tuple[str, ...]
    basis: str

    @property
    def n_days(self) -> int:
        return int(self.kc.size)

    def stage_bands(self) -> list[dict]:
        out = []
        for i, code in enumerate(self.stage_codes):
            idx = np.nonzero(self.stage_idx == i)[0]
            if idx.size:
                out.append({"stage": code, "start": str(self.plant_date + np.timedelta64(int(idx[0]), "D")),
                            "end": str(self.plant_date + np.timedelta64(int(idx[-1]), "D")), "critical": bool(self.critical[idx[0]])})
        return out


def _stage_lengths_from_gdd(v: Variety, tmean_from_plant: np.ndarray) -> list[int] | None:
    gdd = np.cumsum(np.maximum(0.0, np.nan_to_num(tmean_from_plant, nan=0.0) - v.gdd_base_c))
    end_idx = int(np.searchsorted(gdd, v.stages[-1].gdd_end, side="left"))
    if end_idx >= gdd.size or np.any(~np.isfinite(tmean_from_plant[: end_idx + 1])):
        return None  # no se alcanza el total o hay faltantes de T dentro del ciclo: no se inventa
    bounds = [0]
    for s in v.stages:
        k = int(np.searchsorted(gdd, s.gdd_end, side="left")) + 1
        if k > gdd.size:
            return None
        bounds.append(max(k, bounds[-1] + 1))
    return [b - a for a, b in zip(bounds[:-1], bounds[1:])]


def build_calendar(v: Variety, plant_date: np.datetime64, tmean_from_plant: np.ndarray | None = None) -> Calendar | None:
    """Calendario diario de la variedad. None si (gdd) no se alcanza con los datos."""
    plant_date = np.datetime64(plant_date, "D")
    if v.phenology_basis == "days":
        lengths = [int(s.length_days) for s in v.stages]
    else:
        if tmean_from_plant is None:
            raise ValueError("fenología gdd requiere tmean desde la siembra")
        lengths = _stage_lengths_from_gdd(v, np.asarray(tmean_from_plant, dtype=float))
        if lengths is None:
            return None
    stage_idx = np.concatenate([np.full(n, i) for i, n in enumerate(lengths)])
    kc = np.concatenate([
        np.full(n, s.kc_start) if n == 1 else s.kc_start + (s.kc_end - s.kc_start) * np.arange(n) / n
        for s, n in zip(v.stages, lengths)
    ])
    crit = np.concatenate([np.full(n, s.critical) for s, n in zip(v.stages, lengths)])
    n_total = int(sum(lengths))
    for a in (stage_idx, kc, crit):
        a.setflags(write=False)
    return Calendar(v.code, plant_date, plant_date + np.timedelta64(n_total - 1, "D"), stage_idx, kc, crit,
                    tuple(s.code for s in v.stages), v.phenology_basis)


def assert_same_cycle_length(varieties: list[Variety]) -> None:
    """Una variedad por mapa: rechaza mezclar duraciones distintas (MixedCycleLengthError)."""
    sigs = {v.stage_signature() for v in varieties}
    if len(sigs) > 1:
        raise MixedCycleLengthError("Las variedades tienen etapas distintas; elija una por mapa.")


def system_etc_exploratory(components: list[tuple[float, np.ndarray]], et0: np.ndarray) -> np.ndarray:
    """ETc_sistema = Σ f_i·Kc_i·ET0 (aproximación exploratoria, evidencia C)."""
    n = len(et0)
    tot = np.zeros(n)
    for f, kc in components:
        k = np.zeros(n)
        k[: min(n, kc.size)] = kc[:n]
        tot += f * k * et0
    return tot
