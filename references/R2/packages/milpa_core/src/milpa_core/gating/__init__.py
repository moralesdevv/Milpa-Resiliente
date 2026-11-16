"""Gating: el motor decide el modo, único por corrida (apartado 11.1). Nunca inventa datos."""
from __future__ import annotations

from dataclasses import dataclass

from ..crops import Catalogs
from ..enums import MODE_LABEL, Label, Mode, PropertyStatus
from ..soil import SoilContext
from ..strategy import Strategy


@dataclass(frozen=True)
class GatingConfig:
    accepted_awc_ptf: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModeDecision:
    mode: Mode
    label: Label
    reasons: tuple[str, ...]


def decide_mode(soil: SoilContext, strategies: list[Strategy], catalogs: Catalogs, cfg: GatingConfig) -> ModeDecision:
    missing: list[str] = []
    awc = soil.property("awc_mm_m")
    depth = soil.property("effective_depth")
    awc_ok = awc.status is PropertyStatus.MEDIDO or (
        awc.status is PropertyStatus.ESTIMADO and (awc.method in cfg.accepted_awc_ptf)
    )
    if not awc_ok:
        missing.append("awc")
    if depth.status not in (PropertyStatus.MEDIDO, PropertyStatus.DECLARADO):
        missing.append("effective_depth")
    if soil.initial_condition is None:
        missing.append("initial_condition")
    for s in strategies:
        for vcode in s.varieties():
            v = catalogs.varieties[vcode]
            if not v.root_depth_cited or not v.depletion_fraction_cited:
                tag = f"catalog:{v.code}"
                if tag not in missing:
                    missing.append(tag)
    if missing:
        return ModeDecision(Mode.EXPOSURE, MODE_LABEL[Mode.EXPOSURE], tuple(missing))
    return ModeDecision(Mode.ROOT_ZONE, MODE_LABEL[Mode.ROOT_ZONE], ())
