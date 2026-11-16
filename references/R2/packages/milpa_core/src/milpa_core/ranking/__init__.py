"""Ranking multicriterio con soporte común y estabilidad ante pesos (apartados 11.11–11.12)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from ..config import RankingConfig, StabilityConfig
from ..criteria import CriterionValue
from ..enums import CRITERIA, Criterion, CriterionStatus, Evidence, RankingStatus, StabilityFlag
from ..provenance import min_evidence

CRIT_LABEL_ES = {Criterion.WATER: "seguridad hídrica", Criterion.SOIL: "salud del suelo",
                 Criterion.FOOD: "alimentación familiar", Criterion.INCOME: "ingresos"}

INTERPRETATION_ES = ("La estabilidad mide la sensibilidad del orden a variaciones de los pesos de prioridad, "
                     "no la probabilidad de que una estrategia sea la mejor.")


@dataclass(frozen=True)
class RankingResult:
    status: RankingStatus
    order: tuple[str, ...] = ()
    totals: Mapping[str, float] = field(default_factory=dict)
    scores: Mapping[Criterion, Mapping[str, float]] = field(default_factory=dict)
    weights: Mapping[Criterion, float] = field(default_factory=dict)
    weights_effective: Mapping[Criterion, float] = field(default_factory=dict)
    weight_coverage: float | None = None
    criteria_used: tuple[Criterion, ...] = ()
    evidence: Evidence | None = None
    provisional: bool = False
    decision_log: tuple[dict, ...] = ()
    explanations: tuple[dict, ...] = ()
    partial_table: tuple[dict, ...] | None = None
    top_margin: float | None = None
    margin_within_uncertainty: bool | None = None
    ties: tuple[tuple[str, str], ...] = ()
    non_discriminating: tuple[Criterion, ...] = ()
    eligible: tuple[str, ...] = ()
    message: str | None = None


def partial_table(S, E) -> tuple[dict, ...]:
    rows = []
    for s in E:
        rows.append({"strategy": s, **{c.value: {"status": S[s][c].status.value, "value": S[s][c].value} for c in CRITERIA}})
    return tuple(rows)


def normalise(values: Mapping[str, float], scale: tuple[float, float] | None) -> tuple[dict[str, float], bool]:
    """Mayor es mejor. Escala de referencia del catálogo si existe; si no, min–max sobre E."""
    if scale is not None:
        lo, hi = scale
        return {s: float(np.clip((v - lo) / (hi - lo), 0, 1)) for s, v in values.items()}, False
    vs = list(values.values())
    lo, hi = min(vs), max(vs)
    if hi - lo < 1e-12:
        return {s: 0.5 for s in values}, True
    return {s: (v - lo) / (hi - lo) for s, v in values.items()}, False


def _order(E, total, scores) -> list[str]:
    w = scores.get(Criterion.WATER, {})
    return sorted(E, key=lambda s: (-round(total[s], 12), -w.get(s, 0.0), s))


def rank(S: Mapping[str, Mapping[Criterion, CriterionValue]], w: Mapping[Criterion, float], cfg: RankingConfig,
         eligible: Mapping[str, tuple[bool, tuple[str, ...]]] | None = None,
         by_year_crit: Mapping[str, Mapping[int, tuple[int, int]]] | None = None) -> RankingResult:
    log: list[dict] = []
    tot_w = sum(w.values())
    if abs(tot_w - 1.0) > 1e-6:
        raise ValueError(f"los pesos deben sumar 1 ± 1e-6 (suman {tot_w})")
    E = []
    for s in sorted(S):
        ok, why = (eligible or {}).get(s, (True, ()))
        if ok:
            E.append(s)
        else:
            log.append({"decision": "excluida_por_elegibilidad", "strategy": s, "reasons": list(why)})
    if cfg.missing_policy == "exclude_incomplete":
        keep = []
        for s in E:
            miss = [c.value for c in CRITERIA if w.get(c, 0) > 0 and S[s][c].status is CriterionStatus.NOT_EVALUABLE]
            if miss:
                log.append({"decision": "excluida_por_incompleta", "strategy": s, "criteria": miss})
            else:
                keep.append(s)
        E = keep
    if len(E) < 2:
        return RankingResult(RankingStatus.INSUFFICIENT, weights=dict(w), decision_log=tuple(log), eligible=tuple(E),
                             message="menos de dos estrategias elegibles", partial_table=partial_table(S, E))
    C = []
    for c in CRITERIA:
        if w.get(c, 0) <= 0:
            continue
        missing_in = [s for s in E if S[s][c].status is CriterionStatus.NOT_EVALUABLE]
        if missing_in:
            log.append({"decision": "criterio_fuera_del_soporte_comun", "criterion": c.value, "missing_in": missing_in,
                        "note": "sale del total para todas: ninguna gana por tener menos datos"})
        else:
            C.append(c)
    cov = sum(w[c] for c in C)
    if not C or cov < cfg.min_weight_coverage:
        log.append({"decision": "cobertura_de_pesos_insuficiente", "weight_coverage": cov, "min": cfg.min_weight_coverage})
        return RankingResult(RankingStatus.INSUFFICIENT, weights=dict(w), weight_coverage=cov, criteria_used=tuple(C),
                             decision_log=tuple(log), partial_table=partial_table(S, E), eligible=tuple(E),
                             message="criterios comunes insuficientes")
    w_eff = {c: w[c] / cov for c in C}
    scores, nondisc = {}, []
    for c in C:
        sc, nd = normalise({s: S[s][c].value for s in E}, cfg.reference_scales.get(c.value))
        scores[c] = sc
        if nd:
            nondisc.append(c)
            log.append({"decision": "criterio_no_discriminante", "criterion": c.value, "note": "todas reciben 0.5"})
    total = {s: sum(w_eff[c] * scores[c][s] for c in C) for s in E}
    order = _order(E, total, scores)
    ties = tuple((a, b) for a, b in zip(order, order[1:]) if abs(total[a] - total[b]) < cfg.tie_eps)
    ev = min_evidence([S[s][c].evidence for s in E for c in C])
    prov = any(S[s][c].status is CriterionStatus.PROVISIONAL for s in E for c in C)
    expl = []
    for a, b in zip(order, order[1:]):
        contrib = {c.value: w_eff[c] * (scores[c][a] - scores[c][b]) for c in C}
        parts = []
        for c, d in sorted(contrib.items(), key=lambda kv: -abs(kv[1])):
            if abs(d) < 1e-9:
                continue
            win, lose = (a, b) if d > 0 else (b, a)
            parts.append(f"{win} supera a {lose} en {CRIT_LABEL_ES[Criterion(c)]} ({abs(d):+.2f})")
        expl.append({"a": a, "b": b, "contributions": contrib, "text_es": "; ".join(parts) or "sin diferencia"})
    top_margin = total[order[0]] - total[order[1]]
    within = None
    if by_year_crit and Criterion.WATER in C:
        within = margin_within_uncertainty(S, E, C, w_eff, scores, order, by_year_crit, cfg)
    return RankingResult(RankingStatus.OK, tuple(order), total, scores, dict(w), w_eff, cov, tuple(C), ev, prov, tuple(log),
                         tuple(expl), None, top_margin, within, ties, tuple(nondisc), tuple(E))


def margin_within_uncertainty(S, E, C, w_eff, scores, order, by_year_crit, cfg: RankingConfig) -> bool:
    """Bootstrap pareado de años agrícolas sobre el criterio hídrico; True si el IC 90 % de la diferencia incluye 0."""
    a, b = order[0], order[1]
    years = sorted({y for s in (a, b) for y in by_year_crit.get(s, {})})
    if len(years) < 3:
        return True
    rng = np.random.default_rng(cfg.seed)
    diffs = []
    for _ in range(cfg.n_boot):
        ys = rng.choice(years, size=len(years), replace=True)
        wv = {}
        for s in E:
            nc = sum(by_year_crit.get(s, {}).get(int(y), (0, 0))[0] for y in ys)
            nd = sum(by_year_crit.get(s, {}).get(int(y), (0, 0))[1] for y in ys)
            wv[s] = 1 - nc / nd if nd else S[s][Criterion.WATER].value
        ws, _ = normalise(wv, cfg.reference_scales.get(Criterion.WATER.value))
        tot = {s: sum(w_eff[c] * (ws[s] if c is Criterion.WATER else scores[c][s]) for c in C) for s in (a, b)}
        diffs.append(tot[a] - tot[b])
    lo = float(np.percentile(diffs, 5))
    return lo <= 0.0


# ------------------------------------------------------------------ estabilidad

@dataclass(frozen=True)
class StabilityResult:
    flag: StabilityFlag
    top1_share: Mapping[str, float] = field(default_factory=dict)
    rank_corr_mean: float | None = None
    conflicts: tuple[dict, ...] = ()
    n_samples: int = 0
    seed: int = 0
    mode: str = "dirichlet"
    interpretation_es: str = INTERPRETATION_ES


def project_simplex(v: np.ndarray) -> np.ndarray:
    """Proyección euclídea por filas al símplex (Duchi et al. 2008)."""
    v = np.atleast_2d(v)
    n = v.shape[1]
    u = -np.sort(-v, axis=1)
    css = np.cumsum(u, axis=1) - 1
    ind = np.arange(1, n + 1)
    cond = u - css / ind > 0
    rho = n - np.argmax(cond[:, ::-1], axis=1)
    theta = css[np.arange(v.shape[0]), rho - 1] / rho
    return np.maximum(v - theta[:, None], 0)


def kendall_tau(a: list[str], b: list[str]) -> float:
    pos = {s: i for i, s in enumerate(b)}
    n = len(a)
    if n < 2:
        return 1.0
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            if pos[a[i]] < pos[a[j]]:
                conc += 1
            else:
                disc += 1
    return (conc - disc) / (n * (n - 1) / 2)


def rank_stability(base: RankingResult, cfg: StabilityConfig) -> StabilityResult:
    if base.status is RankingStatus.INSUFFICIENT or cfg.n_samples < cfg.min_samples:
        return StabilityResult(StabilityFlag.INSUFFICIENT, n_samples=cfg.n_samples, seed=cfg.seed, mode=cfg.mode)
    rng = np.random.default_rng(cfg.seed)
    C = list(base.weights_effective.keys())  # solo criterios del soporte común
    E = list(base.order)
    w0 = np.array([base.weights_effective[c] for c in C])
    if len(C) == 1:
        Ws = np.ones((cfg.n_samples, 1))
    elif cfg.mode == "dirichlet":
        Ws = rng.dirichlet(cfg.concentration * np.maximum(w0, 1e-6), size=cfg.n_samples)
    else:
        Ws = project_simplex(w0 + rng.uniform(-cfg.radius, cfg.radius, size=(cfg.n_samples, len(C))))
    M = np.array([[base.scores[c][s] for c in C] for s in E])  # estrategias × criterios
    totals = Ws @ M.T  # muestras × estrategias
    wat = np.array([base.scores.get(Criterion.WATER, {}).get(s, 0.0) for s in E])
    orders = []
    for t in totals:
        idx = sorted(range(len(E)), key=lambda i: (-round(t[i], 12), -wat[i], E[i]))
        orders.append([E[i] for i in idx])
    share = Counter(o[0] for o in orders)
    top = {s: n / cfg.n_samples for s, n in share.items()}
    base_share = top.get(base.order[0], 0.0)
    tau = float(np.mean([kendall_tau(list(base.order), o) for o in orders]))
    flag = (StabilityFlag.STABLE if base_share >= cfg.stable_share else
            StabilityFlag.UNSTABLE if base_share < cfg.unstable_share else StabilityFlag.MODERATE)
    conflicts = []
    leader = base.order[0]
    for s, sh in sorted(top.items(), key=lambda kv: -kv[1]):
        if s == leader or sh <= 0:
            continue
        diffs = {c.value: base.scores[c][s] - base.scores[c][leader] for c in C}
        best_c = max(diffs, key=diffs.get)
        worst_c = min(diffs, key=diffs.get)
        conflicts.append({"pair": [leader, s], "challenger_top1_share": sh, "challenger_wins_on": best_c,
                          "leader_wins_on": worst_c,
                          "text_es": f"{s} queda primera cuando pesa más {CRIT_LABEL_ES[Criterion(best_c)]}; "
                                     f"{leader} cuando pesa más {CRIT_LABEL_ES[Criterion(worst_c)]}"})
    return StabilityResult(flag, top, tau, tuple(conflicts), cfg.n_samples, cfg.seed, cfg.mode)


def sample_weights(w0: np.ndarray, cfg: StabilityConfig) -> np.ndarray:
    """Expuesto para T-P06."""
    rng = np.random.default_rng(cfg.seed)
    if cfg.mode == "dirichlet":
        return rng.dirichlet(cfg.concentration * np.maximum(w0, 1e-6), size=cfg.n_samples)
    return project_simplex(w0 + rng.uniform(-cfg.radius, cfg.radius, size=(cfg.n_samples, len(w0))))
