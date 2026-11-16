"""Procedencia y evidencia A/B/C (apartados 15 y 21).

``IndicatorBuilder`` es la ÚNICA forma de crear un ``Indicator``: recibe la
procedencia de sus entradas y calcula la evidencia como mínimo, nunca como máximo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, Iterable

from ..enums import (
    AdaptationMode,
    Evidence,
    HumidityAssumption,
    IndicatorKind,
    Label,
    Provenance,
)
from ..errors import IndicatorContractError


@dataclass(frozen=True)
class SourceRef:
    code: str
    product_name: str = ""
    institution: str = ""
    is_nasa: bool = False
    version: str | None = None
    citation: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class ProvenanceInfo:
    provenance: Provenance
    evidence: Evidence | None
    evidence_rule: str
    method: str
    sources: tuple[SourceRef, ...] = ()
    dataset_version: str | None = None
    period: Period | None = None
    spatial_res: str | None = None
    temporal_res: str | None = None
    retrieved_at: datetime | None = None
    missing_pct: float | None = None
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    run_id: str | None = None

    def __post_init__(self) -> None:
        if self.provenance is Provenance.DESCONOCIDO and self.evidence is not None:
            raise IndicatorContractError("dato desconocido debe tener evidencia nula")
        if self.provenance is not Provenance.DESCONOCIDO and self.evidence is None:
            raise IndicatorContractError("evidencia nula solo con procedencia desconocido")
        if not self.evidence_rule:
            raise IndicatorContractError("evidence_rule obligatorio")


@dataclass(frozen=True)
class ScenarioTag:
    scenario_id: str
    delta_t_c: float
    precip_factor: float
    onset_delay_days: int
    humidity_assumption: HumidityAssumption
    adaptation_mode: AdaptationMode
    method_doc: str
    engine_version: str
    executed_at: str
    label: str = "escenario sintético"


@dataclass(frozen=True)
class Indicator:
    code: str
    label_es: str
    label_en: str
    value: Any
    unit: str
    kind: IndicatorKind
    provenance: ProvenanceInfo
    label: Label | None = None
    provisional: bool = False
    reason: str | None = None
    scenario: ScenarioTag | None = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            raise IndicatorContractError(f"{self.code}: Indicator sin procedencia")
        if self.kind is IndicatorKind.EXPOSURE and self.label is not Label.EXPOSURE_INDICATOR:
            raise IndicatorContractError(f"{self.code}: kind=exposure exige etiqueta de exposición")
        if self.kind is IndicatorKind.ROOT_ZONE and self.label is not Label.ROOT_ZONE_BALANCE:
            raise IndicatorContractError(f"{self.code}: kind=root_zone exige etiqueta de balance")
        if self.kind not in (IndicatorKind.EXPOSURE, IndicatorKind.ROOT_ZONE) and self.label is not None:
            raise IndicatorContractError(f"{self.code}: label solo para exposure/root_zone")
        if self.provisional and not self.reason:
            raise IndicatorContractError(f"{self.code}: provisional=true exige reason")
        if not self.unit:
            raise IndicatorContractError(f"{self.code}: unidad obligatoria")


# ----------------------------------------------------------------- evidencia

def min_evidence(levels: Iterable[Evidence | None]) -> Evidence | None:
    """Mínimo de evidencia. Si alguna entrada es desconocida (None) → None."""
    lv = list(levels)
    if not lv:
        return None
    if any(x is None for x in lv):
        return None
    return min(lv, key=lambda e: e.rank)


def cap_evidence(level: Evidence | None, cap: Evidence) -> Evidence | None:
    if level is None:
        return None
    return level if level.rank <= cap.rank else cap


@dataclass
class IndicatorBuilder:
    """Construye Indicators propagando evidencia mínima de las entradas.

    >>> b = IndicatorBuilder(code="severity_p90_mm", label_es="P90 de severidad", label_en="Severity P90",
    ...                      unit="mm", kind=IndicatorKind.EXPOSURE, label=Label.EXPOSURE_INDICATOR)
    >>> b.from_inputs(rain_prov, et0_prov).rule("risk.min_inputs").method("...").build(12.3)
    """

    code: str
    label_es: str
    label_en: str
    unit: str
    kind: IndicatorKind
    label: Label | None = None
    provenance_kind: Provenance = Provenance.MODELADO
    _inputs: list[ProvenanceInfo] = field(default_factory=list)
    _extra_levels: list[Evidence | None] = field(default_factory=list)
    _cap: Evidence | None = None
    _rule: str = ""
    _method: str = ""
    _assumptions: list[str] = field(default_factory=list)
    _limitations: list[str] = field(default_factory=list)
    _sources: list[SourceRef] = field(default_factory=list)
    _missing_pct: float | None = None
    _period: Period | None = None
    _run_id: str | None = None

    def from_inputs(self, *provs: ProvenanceInfo | None) -> "IndicatorBuilder":
        for p in provs:
            if p is None:
                continue
            self._inputs.append(p)
            for s in p.sources:
                if s not in self._sources:
                    self._sources.append(s)
            self._assumptions += [a for a in p.assumptions if a not in self._assumptions]
            self._limitations += [x for x in p.limitations if x not in self._limitations]
        return self

    def with_level(self, level: Evidence | None) -> "IndicatorBuilder":
        """Evidencia de un parámetro no climático (Kc, umbral, catálogo)."""
        self._extra_levels.append(level)
        return self

    def cap(self, level: Evidence) -> "IndicatorBuilder":
        self._cap = level
        return self

    def rule(self, rule_id: str) -> "IndicatorBuilder":
        self._rule = rule_id
        return self

    def method(self, m: str) -> "IndicatorBuilder":
        self._method = m
        return self

    def assume(self, *a: str) -> "IndicatorBuilder":
        self._assumptions += [x for x in a if x not in self._assumptions]
        return self

    def limit(self, *a: str) -> "IndicatorBuilder":
        self._limitations += [x for x in a if x not in self._limitations]
        return self

    def missing(self, pct: float | None) -> "IndicatorBuilder":
        self._missing_pct = pct
        return self

    def period(self, p: Period | None) -> "IndicatorBuilder":
        self._period = p
        return self

    def run(self, run_id: str | None) -> "IndicatorBuilder":
        self._run_id = run_id
        return self

    def evidence(self) -> Evidence | None:
        ev = min_evidence([p.evidence for p in self._inputs] + self._extra_levels)
        if self._cap is not None:
            ev = cap_evidence(ev, self._cap)
        return ev

    def build(self, value: Any, *, provisional: bool = False, reason: str | None = None,
              scenario: ScenarioTag | None = None) -> Indicator:
        ev = self.evidence()
        prov_kind = self.provenance_kind if ev is not None else Provenance.DESCONOCIDO
        pinfo = ProvenanceInfo(
            provenance=prov_kind,
            evidence=ev,
            evidence_rule=self._rule or "unspecified",
            method=self._method,
            sources=tuple(self._sources),
            period=self._period,
            missing_pct=self._missing_pct,
            assumptions=tuple(self._assumptions),
            limitations=tuple(self._limitations),
            run_id=self._run_id,
        )
        return Indicator(
            code=self.code, label_es=self.label_es, label_en=self.label_en, value=value,
            unit=self.unit, kind=self.kind, provenance=pinfo, label=self.label,
            provisional=provisional, reason=reason, scenario=scenario,
        )


def with_scenario(ind: Indicator, tag: ScenarioTag | None) -> Indicator:
    return replace(ind, scenario=tag)


__all__ = [
    "SourceRef", "Period", "ProvenanceInfo", "ScenarioTag", "Indicator", "IndicatorBuilder",
    "min_evidence", "cap_evidence", "with_scenario",
]
