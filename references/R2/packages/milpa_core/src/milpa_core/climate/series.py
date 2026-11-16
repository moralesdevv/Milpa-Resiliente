"""Series climáticas inmutables que entran al motor.

``ClimateSeries``: serie diaria curada por R1 (``curated/<zona>/daily.parquet``) de una
celda. ``derive_climate`` calcula ET0 (dos rutas de ea) y Pef diaria por método y
devuelve ``CuratedClimate``, que es lo que consumen exposure/rootzone/scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import numpy as np

from ..enums import EaMethod, Evidence, PeffMethod, Provenance, QcFlag, Reason
from ..provenance import ProvenanceInfo, SourceRef, cap_evidence, min_evidence
from .dekad import dekad_of, doy
from .et0 import actual_vp, es_from, et0_fao56, extraterrestrial_radiation, hargreaves_rs
from .peff import pef_daily

MET_VARS = ("tmax_c", "tmin_c", "wind2m_ms", "srad_mj_m2")  # ET0_INPUTS (humedad aparte)


def _ro(a) -> np.ndarray:
    arr = np.array(a, copy=True)
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True)
class ClimateSeries:
    dates: np.ndarray  # datetime64[D], continuo
    tmax_c: np.ndarray
    tmin_c: np.ndarray
    precip_mm: np.ndarray
    wind2m_ms: np.ndarray
    srad_mj_m2: np.ndarray
    tdew_c: np.ndarray | None = None
    rh_pct: np.ndarray | None = None
    qc_flags: np.ndarray | None = None
    precip_prov: ProvenanceInfo | None = None
    met_prov: ProvenanceInfo | None = None
    cell_id: str = "cell"

    def __post_init__(self) -> None:
        n = len(self.dates)
        for name in ("tmax_c", "tmin_c", "precip_mm", "wind2m_ms", "srad_mj_m2", "tdew_c", "rh_pct", "qc_flags"):
            v = getattr(self, name)
            if v is None:
                continue
            if len(v) != n:
                raise ValueError(f"{name}: longitud {len(v)} ≠ {n}")
            object.__setattr__(self, name, _ro(v))
        d = np.asarray(self.dates, dtype="datetime64[D]")
        if n > 1 and not np.all(np.diff(d).astype(int) == 1):
            raise ValueError("la serie diaria debe ser continua (faltantes como NaN, no días ausentes)")
        object.__setattr__(self, "dates", _ro(d))
        if self.precip_prov is None:
            object.__setattr__(self, "precip_prov", default_precip_prov())
        if self.met_prov is None:
            object.__setattr__(self, "met_prov", default_met_prov())

    def index_of(self, day: np.datetime64) -> int:
        return int((np.datetime64(day, "D") - self.dates[0]).astype(int))

    @property
    def start(self) -> np.datetime64:
        return self.dates[0]

    @property
    def end(self) -> np.datetime64:
        return self.dates[-1]


def default_precip_prov() -> ProvenanceInfo:
    return ProvenanceInfo(
        provenance=Provenance.SATELITAL, evidence=Evidence.C, evidence_rule="precip.imerg.sin_validacion_local",
        method="IMERG Final V07 diario; sin validación con estación en la zona",
        sources=(SourceRef("IMERG_FINAL_V07", "GPM IMERG Final Run", "NASA GES DISC", True, "V07"),),
        spatial_res="0.1°", temporal_res="diaria",
        limitations=("sin validación con estación local (evidencia C)",),
    )


def default_met_prov() -> ProvenanceInfo:
    return ProvenanceInfo(
        provenance=Provenance.MODELADO, evidence=Evidence.B, evidence_rule="met.power.reanalisis",
        method="NASA POWER diario (MERRA-2/CERES)",
        sources=(SourceRef("POWER_DAILY", "NASA POWER Daily", "NASA LaRC", True),),
        spatial_res="0.5°×0.625°", temporal_res="diaria",
    )


@dataclass(frozen=True)
class CuratedClimate:
    base: ClimateSeries
    lat_deg: float
    elevation_m: float
    et0_mm: np.ndarray
    ea_kpa: np.ndarray
    ea_method: np.ndarray
    rad_modeled: np.ndarray
    pef_day: Mapping[str, np.ndarray]  # método → Pef diaria asignada
    dekad_key: np.ndarray
    et0_prov: ProvenanceInfo
    pef_prov: Mapping[str, ProvenanceInfo]
    ea_route_diff_pct: float | None = None  # diferencia estacional entre rutas
    flags: tuple[str, ...] = ()
    scenario_id: str = "BASE"
    mass_dropped_mm: float = 0.0
    onset_day_idx: Mapping[int, int] = field(default_factory=dict)  # agri_year → índice t0 (escenarios)

    # accesos cómodos
    @property
    def dates(self) -> np.ndarray:
        return self.base.dates

    @property
    def precip_mm(self) -> np.ndarray:
        return self.base.precip_mm

    def tmean_c(self) -> np.ndarray:
        return (self.base.tmax_c + self.base.tmin_c) / 2.0

    def sl(self, start: np.datetime64, end_inclusive: np.datetime64) -> slice:
        i0 = self.base.index_of(start)
        i1 = self.base.index_of(end_inclusive) + 1
        return slice(i0, i1)

    def covers(self, start: np.datetime64, end_inclusive: np.datetime64) -> bool:
        return start >= self.dates[0] and end_inclusive <= self.dates[-1]


def compute_et0(s: ClimateSeries, lat_deg: float, elevation_m: float, krs: float = 0.16):
    ea, ea_m, capped = actual_vp(s.tmax_c, s.tmin_c, s.tdew_c, s.rh_pct)
    j = doy(s.dates)
    rs = np.asarray(s.srad_mj_m2, dtype=float)
    rad_mod = ~np.isfinite(rs)
    if s.qc_flags is not None:
        rad_mod |= (np.asarray(s.qc_flags).astype(int) & QcFlag.RAD_MODELED) > 0
    if np.any(~np.isfinite(rs)):
        ra = extraterrestrial_radiation(lat_deg, j)
        rs = np.where(np.isfinite(rs), rs, hargreaves_rs(s.tmax_c, s.tmin_c, ra, krs))
    et0, _neg = et0_fao56(s.tmax_c, s.tmin_c, rs, s.wind2m_ms, ea, elevation_m, lat_deg, j)
    return et0, ea, ea_m, rad_mod


def ea_route_difference(s: ClimateSeries, lat_deg: float, elevation_m: float) -> float | None:
    """Diferencia relativa (%) de ET0 total entre rutas de ea; None si falta alguna ruta."""
    if s.tdew_c is None or s.rh_pct is None:
        return None
    j = doy(s.dates)
    e1, *_ = actual_vp(s.tmax_c, s.tmin_c, s.tdew_c, None)
    es = es_from(s.tmax_c, s.tmin_c)
    e2 = np.minimum(np.asarray(s.rh_pct) / 100.0 * es, es)
    a, _ = et0_fao56(s.tmax_c, s.tmin_c, s.srad_mj_m2, s.wind2m_ms, e1, elevation_m, lat_deg, j)
    b, _ = et0_fao56(s.tmax_c, s.tmin_c, s.srad_mj_m2, s.wind2m_ms, e2, elevation_m, lat_deg, j)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() == 0:
        return None
    return float(100.0 * abs(a[ok].sum() - b[ok].sum()) / max(b[ok].sum(), 1e-9))


def derive_climate(
    s: ClimateSeries,
    lat_deg: float,
    elevation_m: float,
    peff_methods: tuple[PeffMethod, ...] | list[PeffMethod],
    phi: float | None = None,
    ea_sensitivity_tol_pct: float | None = None,
    peff_citations: Mapping[str, Evidence] | None = None,
    scenario_id: str = "BASE",
) -> CuratedClimate:
    et0, ea, ea_m, rad_mod = compute_et0(s, lat_deg, elevation_m)
    flags: list[str] = []
    diff = ea_route_difference(s, lat_deg, elevation_m)
    lim = []
    if diff is not None and ea_sensitivity_tol_pct is not None and diff > ea_sensitivity_tol_pct:
        flags.append(Reason.EA_SENSIBLE_A_LA_RUTA.value)
        lim.append(Reason.EA_SENSIBLE_A_LA_RUTA.value)
    share_rh = float(np.mean(ea_m == EaMethod.RH_MEAN.value)) if len(ea_m) else 0.0
    ev = s.met_prov.evidence
    rule = "et0.fao56.power"
    if np.any(rad_mod):
        ev = cap_evidence(ev, Evidence.C)
        rule = "et0.fao56.rs_hargreaves"
        lim.append("radiación modelada por Hargreaves–Samani en parte de la serie")
    et0_prov = ProvenanceInfo(
        provenance=Provenance.MODELADO, evidence=ev, evidence_rule=rule,
        method=f"FAO56-PM; ea=dewpoint (fallback RH2M en {share_rh:.0%} de días); P con elevación DEM {elevation_m:.0f} m",
        sources=s.met_prov.sources, assumptions=("G = 0 en paso diario", "ajuste climático de Kc desactivado (sin RHmin)"),
        limitations=tuple(lim) + ("ET0 es modelada, no medida",),
    )
    pef_day: dict[str, np.ndarray] = {}
    pef_prov: dict[str, ProvenanceInfo] = {}
    for m in peff_methods:
        m = PeffMethod(m)
        if m is PeffMethod.FIXED_FRACTION and phi is None:
            continue
        arr = pef_daily(s.dates, s.precip_mm, m, phi)
        arr.setflags(write=False)
        pef_day[m.value] = arr
        cit = (peff_citations or {}).get(m.value, Evidence.C)
        pev = min_evidence([s.precip_prov.evidence, cit])
        pef_prov[m.value] = ProvenanceInfo(
            provenance=Provenance.MODELADO, evidence=pev, evidence_rule=f"pef.{m.value}.min_insumos",
            method=f"Pef={m.value} en escala nativa, desagregada por P_d/P_mes",
            sources=s.precip_prov.sources,
            limitations=("la desagregación a decenas es una asignación, no un proceso físico",),
        )
    _, _, dk = dekad_of(s.dates)
    return CuratedClimate(
        base=s, lat_deg=lat_deg, elevation_m=elevation_m, et0_mm=_ro(et0), ea_kpa=_ro(ea), ea_method=_ro(ea_m),
        rad_modeled=_ro(rad_mod), pef_day=pef_day, dekad_key=_ro(dk), et0_prov=et0_prov, pef_prov=pef_prov,
        ea_route_diff_pct=diff, flags=tuple(flags), scenario_id=scenario_id,
    )


def replace_series(s: ClimateSeries, **kw) -> ClimateSeries:
    return replace(s, **kw)
