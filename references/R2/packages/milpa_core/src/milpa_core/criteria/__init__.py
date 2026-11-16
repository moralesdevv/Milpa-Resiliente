"""Elegibilidad y criterios (apartado 11.10). Valores desconocidos nunca son cero.

Orientación: todos los ``value`` se devuelven como «mayor es mejor».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..config import SoilCriterionConfig
from ..crops import Catalogs
from ..enums import Criterion, CriterionStatus, Evidence, PropertyStatus
from ..provenance import min_evidence
from ..risk import StrategyRisk
from ..soil import SoilContext
from ..strategy import Strategy

SOIL_SUBINDICATORS = ("n_fixation_potential", "cover_months", "family_diversity", "residue_return",
                      "family_repeat_penalty", "ph_compat")


@dataclass(frozen=True)
class CriterionValue:
    criterion: Criterion
    status: CriterionStatus
    value: float | None
    evidence: Evidence | None
    unit: str = "índice 0–1"
    subindicators: Mapping[str, float | None] = field(default_factory=dict)
    reason: str | None = None
    coverage: float | None = None


def not_evaluable(c: Criterion, reason: str) -> CriterionValue:
    return CriterionValue(c, CriterionStatus.NOT_EVALUABLE, None, None, reason=reason)


# ------------------------------------------------------------------ elegibilidad

@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...]
    ph_dependency: bool = False


def ph_compat(ph: float, crop: str, catalogs: Catalogs) -> float | None:
    """Trapezoidal: 1 en el óptimo, lineal a 0 en el absoluto; None si no hay matriz con cita."""
    t = catalogs.ph_tolerance.get(crop)
    if t is None or not t.citation:
        return None
    if ph < t.ph_abs_min or ph > t.ph_abs_max:
        return 0.0
    if t.ph_opt_min <= ph <= t.ph_opt_max:
        return 1.0
    if ph < t.ph_opt_min:
        return (ph - t.ph_abs_min) / max(t.ph_opt_min - t.ph_abs_min, 1e-9)
    return (t.ph_abs_max - ph) / max(t.ph_abs_max - t.ph_opt_max, 1e-9)


def eligibility(s: Strategy, catalogs: Catalogs, soil: SoilContext, crops_enabled: tuple[str, ...] | None,
                ph_override: float | None = None) -> Eligibility:
    reasons = []
    crops = {catalogs.varieties[v].crop for v in s.varieties()}
    if crops_enabled is not None:
        off = sorted(c for c in crops if c not in crops_enabled)
        if off:
            reasons.append("cultivo_no_habilitado:" + ",".join(off))
    if not s.enabled_by_farmer:
        reasons.append("restriccion_declarada:" + (s.farmer_constraint_reason or "sin detalle"))
    ph = soil.property("ph")
    dep = False
    ph_val = ph_override if ph_override is not None else (
        ph.value if ph.status in (PropertyStatus.MEDIDO, PropertyStatus.ESTIMADO) else None)
    if ph_val is None:
        dep = True  # con pH desconocido no se excluye nada; se marca la dependencia
    else:
        for c in crops:
            comp = ph_compat(ph_val, c, catalogs)
            if comp == 0.0:
                reasons.append(f"ph_fuera_de_rango_absoluto:{c}")
    return Eligibility(not reasons, tuple(reasons), dep)


# ------------------------------------------------------------------ criterios

def water_criterion(sr: StrategyRisk | None) -> CriterionValue:
    """Seguridad hídrica = 1 − proporción de ciclos-instancia críticos agrupada (invariante al horizonte)."""
    if sr is None or sr.insufficient or sr.pooled_critical_share_pct is None:
        return not_evaluable(Criterion.WATER, "datos_insuficientes")
    st = CriterionStatus.PROVISIONAL if sr.provisional else CriterionStatus.EVALUABLE
    return CriterionValue(Criterion.WATER, st, 1.0 - sr.pooled_critical_share_pct / 100.0, sr.evidence,
                          subindicators={"pooled_critical_share_pct": sr.pooled_critical_share_pct,
                                         "p90_severity_by_agri_year_mm": sr.p90_severity_by_agri_year_mm,
                                         "tail_ratio": sr.tail_ratio},
                          reason="umbral provisional" if sr.provisional else None)


def _soil_raw(s: Strategy, catalogs: Catalogs, soil: SoilContext, ph_override: float | None) -> dict[str, tuple[float | None, Evidence | None]]:
    out: dict[str, tuple[float | None, Evidence | None]] = {}
    comps = [comp for c in s.cycles for comp in c.components]
    crops = [catalogs.crops[catalogs.varieties[c.variety].crop] for c in comps]
    # potencial de aporte de N: solo si el catálogo declara condiciones para las leguminosas
    legumes = [c for c in crops if c.is_legume]
    if not legumes:
        out["n_fixation_potential"] = (0.0, Evidence.C)
    elif all(c.fixes_n_conditions for c in legumes):
        out["n_fixation_potential"] = (1.0, Evidence.C)
    else:
        out["n_fixation_potential"] = (None, None)
    # meses de cobertura por año agrícola (derivado del calendario; fenología en días)
    days = 0
    ok = True
    for c in s.cycles:
        lens = [catalogs.varieties[comp.variety].cycle_days for comp in c.components]
        if any(x is None for x in lens):
            ok = False
            break
        days += max((comp.plant_offset_days + catalogs.varieties[comp.variety].cycle_days) for comp in c.components)
    out["cover_months"] = ((days / s.horizon_years / 30.44) / 12.0, Evidence.C) if ok else (None, None)
    fams = {c.family for c in crops if c.family}
    out["family_diversity"] = (min(len(fams) / 3.0, 1.0), Evidence.C) if fams else (None, None)
    rr = [c.residue_return for c in crops]
    out["residue_return"] = (sum(rr) / len(rr), Evidence.C) if rr and all(x is not None for x in rr) and \
        all(c.residue_citation for c in crops) else (None, None)
    if soil.previous_crop_family:
        first = crops[0].family if crops else None
        out["family_repeat_penalty"] = (0.0 if first == soil.previous_crop_family else 1.0, Evidence.C)
    else:
        out["family_repeat_penalty"] = (None, None)
    ph = soil.property("ph")
    ph_val = ph_override if ph_override is not None else (
        ph.value if ph.status in (PropertyStatus.MEDIDO, PropertyStatus.ESTIMADO) else None)
    if ph_val is None:
        out["ph_compat"] = (None, None)
    else:
        vals = [ph_compat(ph_val, c.code, catalogs) for c in crops]
        if any(v is None for v in vals):
            out["ph_compat"] = (None, None)
        else:
            evs = [catalogs.ph_tolerance[c.code].evidence for c in crops]
            out["ph_compat"] = (min(vals), min_evidence(evs + [ph.evidence or Evidence.C]))
    return out


def soil_criteria(strategies: list[Strategy], catalogs: Catalogs, soil: SoilContext, cfg: SoilCriterionConfig,
                  ph_override: float | None = None) -> dict[str, CriterionValue]:
    """Media de subindicadores disponibles comunes a todas las estrategias; coverage visible."""
    raw = {s.code: _soil_raw(s, catalogs, soil, ph_override) for s in strategies}
    common = [k for k in SOIL_SUBINDICATORS if all(raw[s][k][0] is not None for s in raw)]
    cov = len(common) / len(SOIL_SUBINDICATORS)
    out = {}
    for s, r in raw.items():
        subs = {k: r[k][0] for k in SOIL_SUBINDICATORS}
        if not common or cov < cfg.min_subindicator_coverage:
            out[s] = CriterionValue(Criterion.SOIL, CriterionStatus.NOT_EVALUABLE, None, None, subindicators=subs,
                                    reason=f"cobertura de subindicadores {cov:.2f} < mínimo", coverage=cov)
            continue
        val = sum(r[k][0] for k in common) / len(common)
        out[s] = CriterionValue(Criterion.SOIL, CriterionStatus.EVALUABLE, val, min_evidence([r[k][1] for k in common]),
                                subindicators=subs, coverage=cov, reason="subindicadores usados: " + ",".join(common))
    return out


def food_criterion(s: Strategy, catalogs: Catalogs) -> CriterionValue:
    kcal = prot = 0.0
    evs = []
    for c in s.cycles:
        for comp in c.components:
            v = catalogs.varieties[comp.variety]
            y = catalogs.reference_yields_kg_ha.get(v.code)
            fc = catalogs.food_composition.get(v.crop)
            if y is None or fc is None:
                return not_evaluable(Criterion.FOOD, "sin rendimiento de referencia o composición con cita")
            kcal += y[0] * comp.area_fraction * fc[0]
            prot += y[0] * comp.area_fraction * fc[1]
            evs.append(y[1])
    h = s.horizon_years
    return CriterionValue(Criterion.FOOD, CriterionStatus.EVALUABLE, kcal / h, min_evidence(evs + [Evidence.C]), "kcal/ha/año",
                          {"kcal_per_ha_year": kcal / h, "protein_g_per_ha_year": prot / h},
                          reason="rendimientos de REFERENCIA, no predicción")


def income_criterion(s: Strategy, catalogs: Catalogs) -> CriterionValue:
    gross = cost = 0.0
    have_costs = True
    for c in s.cycles:
        for comp in c.components:
            v = catalogs.varieties[comp.variety]
            y = catalogs.reference_yields_kg_ha.get(v.code)
            pr = catalogs.prices.get(v.crop)
            if y is None or pr is None:
                return not_evaluable(Criterion.INCOME, "sin precios con fuente; comparación cualitativa")
            gross += y[0] * comp.area_fraction * pr[0]
            vc = catalogs.variable_costs_ha.get(v.crop)
            if vc is None:
                have_costs = False
            else:
                cost += vc[0] * comp.area_fraction
    h = s.horizon_years
    if have_costs:
        return CriterionValue(Criterion.INCOME, CriterionStatus.EVALUABLE, (gross - cost) / h, Evidence.C, "moneda/ha/año",
                              {"margen_bruto": (gross - cost) / h, "ingreso_bruto": gross / h})
    return CriterionValue(Criterion.INCOME, CriterionStatus.EVALUABLE, gross / h, Evidence.C, "moneda/ha/año",
                          {"ingreso_bruto": gross / h}, reason="ingreso_bruto (sin costos: no es margen)")


def build_criteria(strategies: list[Strategy], risks: Mapping[str, StrategyRisk], catalogs: Catalogs, soil: SoilContext,
                   soil_cfg: SoilCriterionConfig = SoilCriterionConfig(), ph_override: float | None = None
                   ) -> dict[str, dict[Criterion, CriterionValue]]:
    soil_c = soil_criteria(strategies, catalogs, soil, soil_cfg, ph_override)
    return {
        s.code: {
            Criterion.WATER: water_criterion(risks.get(s.code)),
            Criterion.SOIL: soil_c[s.code],
            Criterion.FOOD: food_criterion(s, catalogs),
            Criterion.INCOME: income_criterion(s, catalogs),
        }
        for s in strategies
    }
