"""Adaptador ``ReportModel`` (milpa_core, R2) → ``ReportInput`` (plantilla de R3).

Solo reordena y redacta con las cifras que ya calculó el motor: no calcula nada científico. Cada
línea cita la cifra tal como llega (valor, unidad, nivel de evidencia). Lo que el motor no entrega
no se rellena: se dice qué falta. Los textos son bilingües (ES + EN) y las tablas llevan unidades.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from api.reports.contract import (
    ReferenceItem,
    ReportInput,
    ReportSection,
    ReportTable,
    RunHashes,
)

NAMES_EN = {
    "E1_REF_MAIZ": "Reference: first-season maize",
    "E2_MILPA": "Milpa: maize with associated beans",
    "E3_MAIZ_FRIJOL_POSTRERA": "First-season maize, second-season beans",
    "E4_MAIZ_INTERMEDIO": "Intermediate-cycle maize",
    "E5_MAIZ_TARDIO": "Late-planted first-season maize",
    "E6_SORGO": "First-season sorghum",
    "E7_ROTACION_2A": "Two-year rotation: maize → sorghum",
}
CRITERIA = {
    "water": ("seguridad hídrica", "water security"),
    "soil": ("salud del suelo", "soil health"),
    "food": ("alimento del hogar", "household food"),
    "income": ("ingreso", "income"),
}
# Tipo de evidencia de cada cifra (taxonomía visible: observado / satélite-reanálisis / derivado /
# declarado / hipotético / no disponible). «hipotético» = escenario sintético.
PROVENANCE_LABEL = {
    "medido": ("Observado o medido", "Observed or measured"),
    "satelital": ("Satélite o reanálisis", "Satellite or reanalysis"),
    "estimado": ("Estimado", "Estimated"),
    "modelado": ("Derivado o modelado", "Derived or modelled"),
    "declarado": ("Declarado", "Declared"),
    "desconocido": ("No disponible", "Not available"),
}
HYPOTHETICAL = ("Hipotético (escenario sintético)", "Hypothetical (synthetic scenario)")
# Motivos que el motor entrega en español; se traducen solo los que se conocen.
REASONS_EN = {
    "umbral provisional": "provisional threshold (uncited)",
    "umbral provisional — no usar para decisión": "provisional threshold: do not use for decisions",
    "sin rendimiento de referencia o composición con cita": "no cited reference yield or food composition",
    "sin precios con fuente; comparación cualitativa": "no sourced prices; qualitative comparison only",
    "ingreso_bruto (sin costos: no es margen)": "gross income (no costs: not a margin)",
    "rendimientos de REFERENCIA, no predicción": "REFERENCE yields, not a prediction",
}
DECISIONS = {
    "criterio_fuera_del_soporte_comun": (
        "Criterio fuera del soporte común",
        "Criterion outside the common support",
        "sale del total para todas las estrategias: ninguna gana por tener menos datos",
        "left out of the total for every strategy: none wins for having less data",
    ),
    "criterio_no_discriminante": (
        "Criterio no discriminante",
        "Non-discriminating criterion",
        "todas las estrategias reciben el mismo valor",
        "every strategy receives the same value",
    ),
    "cobertura_de_pesos_insuficiente": (
        "Cobertura de pesos insuficiente",
        "Insufficient weight coverage",
        "los criterios con evidencia no cubren el mínimo de peso exigido",
        "the criteria with evidence do not reach the minimum weight required",
    ),
    "excluida_por_elegibilidad": (
        "Estrategia excluida por elegibilidad",
        "Strategy excluded for eligibility",
        "no cumple las condiciones de elegibilidad",
        "does not meet the eligibility conditions",
    ),
    "excluida_por_incompleta": (
        "Estrategia excluida por datos incompletos",
        "Strategy excluded for incomplete data",
        "le faltan criterios evaluables",
        "it lacks evaluable criteria",
    ),
}
MODE_LABEL = {
    "exposure": ("exposición climática", "climate exposure"),
    "root_zone": ("balance hídrico de la zona radicular", "root-zone water balance"),
}
MODE_REASONS = {
    "awc": (
        "capacidad de agua disponible (AWC) del suelo no declarada",
        "soil available water capacity (AWC) not declared",
    ),
    "effective_depth": (
        "profundidad efectiva de raíces no declarada",
        "effective rooting depth not declared",
    ),
    "initial_condition": (
        "condición inicial de humedad del suelo no declarada",
        "initial soil-moisture condition not declared",
    ),
}
STATUS_LABEL = {
    "evaluable": ("evaluable", "evaluable"),
    "provisional": ("provisional (umbral sin cita)", "provisional (uncited threshold)"),
    "not_evaluable": ("no evaluable", "not evaluable"),
}
INDICATOR_LABEL_ES = {
    "annual_precip_mm": "Precipitación anual",
    "annual_et0_mm": "ET0 anual (FAO-56)",
    "valid_days": "Días de lluvia válidos",
}
ND = "n/d"  # no disponible: el motor no entregó el dato (nunca se rellena con 0)


def _cut(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _n(value: Any, digits: int = 1) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return ND
    return f"{float(value):.{digits}f}"


UNIT_SHORT = {"adimensional": "adim."}


def _ind(indicator: Any) -> tuple[Any, str, str]:
    """(valor, unidad, evidencia) tal como los entrega el motor; sin valor ⇒ ``None``."""
    if not isinstance(indicator, Mapping):
        return None, "", "?"
    prov = indicator.get("provenance") or {}
    unit = str(indicator.get("unit") or "")
    return indicator.get("value"), UNIT_SHORT.get(unit, unit), str(prov.get("evidence") or "—")


def _en(name: str, es: str) -> str:
    return NAMES_EN.get(name, es)


def first_anchor_per_strategy(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    seen: dict[str, Mapping[str, Any]] = {}
    for row in sorted(rows, key=lambda r: str(r.get("anchor_md") or "")):
        seen.setdefault(str(row.get("strategy")), row)
    return sorted(seen.values(), key=lambda r: str(r.get("strategy")))


def _bi(both: bool, es: str, en: str) -> str:
    """Texto bilingüe «es / en». Cada mitad se limpia de « / » propias para que la separación sea inequívoca."""
    es = es.replace(" / ", " · ")
    return f"{es} / {en.replace(' / ', ' · ')}" if both else es


def _section(
    both: bool,
    es_title: str,
    en_title: str,
    es_body: str,
    en_body: str,
    items: Sequence[tuple[str, str]] = (),
    table: ReportTable | None = None,
) -> ReportSection:
    return ReportSection(
        title_es=es_title,
        title_en=en_title,
        body_es=es_body,
        body_en=en_body,
        items=[_cut(es) for es, _ in items],
        items_en=[_cut(en) for _, en in items] if items else [],
        table=table,
    )


def _provenance_label(indicator: Mapping[str, Any]) -> tuple[str, str]:
    if indicator.get("scenario"):
        return HYPOTHETICAL
    prov = (indicator.get("provenance") or {}).get("provenance")
    return PROVENANCE_LABEL.get(str(prov), PROVENANCE_LABEL["desconocido"])


def _source_text(prov: Mapping[str, Any]) -> str:
    parts = []
    for src in prov.get("sources") or []:
        if not isinstance(src, Mapping):
            continue
        name = " ".join(
            x for x in (src.get("product_name"), src.get("version")) if x and str(x) != "None"
        )
        inst = src.get("institution")
        parts.append(f"{name} ({inst})" if inst else str(name))
    return (
        "; ".join(parts) or "fuente no registrada por el motor / source not recorded by the engine"
    )


_PROV_FIELDS = {
    "dataset_version": ("versión", "version"),
    "period": ("periodo", "period"),
    "spatial_res": ("resolución espacial", "spatial resolution"),
    "temporal_res": ("resolución temporal", "temporal resolution"),
    "retrieved_at": ("fecha de descarga", "download date"),
    "missing_pct": ("% faltante", "% missing"),
}


def _not_recorded(prov: Mapping[str, Any]) -> frozenset[str]:
    """Metadatos de procedencia que el motor NO registró para este indicador."""
    return frozenset(k for k in _PROV_FIELDS if prov.get(k) in (None, ""))


def _reason_text(reason: str, both: bool) -> str:
    if not both:
        return reason
    if reason in REASONS_EN:
        return f"{reason} / {REASONS_EN[reason]}"
    if reason.startswith("subindicadores usados:"):
        return f"{reason} / sub-indicators used:{reason.split(':', 1)[1]}"
    return reason


def _mode_reason(code: str) -> tuple[str, str]:
    if code in MODE_REASONS:
        return MODE_REASONS[code]
    if code.startswith("catalog:"):
        crop = code.split(":", 1)[1]
        return (
            f"catálogo del cultivo «{crop}» sin parámetros con cita (umbrales y Kc provisionales)",
            f"crop catalog «{crop}» without cited parameters (provisional thresholds and Kc)",
        )
    return _cut(code), _cut(code)


def _not_recorded_items(per_indicator: Sequence[frozenset[str]]) -> list[tuple[str, str]]:
    """Qué metadatos NO registró el motor en NINGÚN indicador (se dice, no se rellena ni se rotula «desconocido»)."""
    if not per_indicator:
        return []
    always = frozenset.intersection(*per_indicator)
    if not always:
        return []
    keys = [k for k in _PROV_FIELDS if k in always]
    es = ", ".join(_PROV_FIELDS[k][0] for k in keys)
    en = ", ".join(_PROV_FIELDS[k][1] for k in keys)
    return [
        (
            f"El motor no registra, para ninguno de estos indicadores: {es}. No se rellenan ni se suponen.",
            f"The engine does not record, for any of these indicators: {en}. They are neither filled in nor assumed.",
        )
    ]


def _risk_rows(model: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    by_id = {str(s.get("id")): s for s in [*model.get("sections", []), *model.get("annex", [])]}
    return first_anchor_per_strategy(list(by_id.get("riesgo", {}).get("content") or []))


def _scenario_label(row: Mapping[str, Any]) -> str:
    return (
        f"{row.get('scenario_id')}: ΔT {row.get('delta_t_c')} °C, "
        f"P \u00d7{row.get('precip_factor')}, retraso {row.get('onset_delay_days')} d"
    )


def report_input_from_model(  # noqa: PLR0915 - constructor de documento: una sección tras otra
    model: Mapping[str, Any],
    *,
    zone_name: str,
    run_id: UUID,
    hashes: RunHashes,
    locale: str,
    privacy_level: str,
    scenario_id: str = "BASE",
    now: datetime | None = None,
    climate: Mapping[str, Any] | None = None,
    coverage: Sequence[Mapping[str, Any]] | None = None,
    data_window: Mapping[str, Any] | None = None,
    scenarios: Sequence[Mapping[str, Any]] | None = None,
) -> ReportInput:
    """Construye el informe. ``climate``/``coverage``/``data_window``/``scenarios`` son opcionales: si faltan,
    el informe lo dice (no inventa cobertura ni escenarios)."""
    both = locale != "es"
    by_id = {str(s.get("id")): s for s in [*model.get("sections", []), *model.get("annex", [])]}
    risk_rows = _risk_rows(model)
    all_risk = list(by_id.get("riesgo", {}).get("content") or [])
    summary = by_id.get("resumen", {}).get("content") or {}
    rank = by_id.get("ranking", {}).get("content")
    rank = rank if isinstance(rank, Mapping) else None
    voi = by_id.get("suelo", {}).get("content")
    prov_meta = by_id.get("procedencia", {}).get("content") or {}
    limitations = [str(x) for x in (by_id.get("supuestos", {}).get("content") or [])]
    reasons = [str(x) for x in (by_id.get("modo", {}).get("content") or [])]
    decision_log = list(by_id.get("decisiones", {}).get("content") or [])
    mode = str(summary.get("modo", "exposure"))
    mode_es, mode_en = MODE_LABEL.get(mode, (mode, mode))
    period = prov_meta.get("period") or []
    period_text = f"{period[0]} → {period[1]}" if len(period) == 2 else "no registrado por el motor"
    n_strat = len(risk_rows)
    criteria_used = [str(c) for c in (rank or {}).get("criteria_used", [])]
    used_es = ", ".join(CRITERIA.get(c, (c, c))[0] for c in criteria_used) or "ninguno"
    used_en = ", ".join(CRITERIA.get(c, (c, c))[1] for c in criteria_used) or "none"
    missing_criteria = [c for c in CRITERIA if c not in criteria_used] if rank else list(CRITERIA)

    sections: list[ReportSection] = []

    # ------------------------------------------------------------------ resumen
    sections.append(
        _section(
            both,
            "Alcance y lectura del informe",
            "Scope and how to read this report",
            f"Comparación de {n_strat} estrategias en la zona {zone_name}. Resultado provisional (modo sandbox, evidencia C).",
            f"Comparison of {n_strat} strategies for zone {zone_name}. Provisional result (sandbox mode, evidence level C).",
            [
                (
                    f"Periodo analizado: {period_text}. Escenario del informe: {scenario_id}.",
                    f"Period analysed: {period_text}. Scenario of this report: {scenario_id}.",
                ),
                (
                    f"Indicador de {mode_es}: no es déficit real de agua del suelo, ni pronóstico, ni estimación de rendimiento.",
                    f"Indicator of {mode_en}: it is not an actual soil-water deficit, a forecast or a yield estimate.",
                ),
                (
                    f"El ranking usa solo los criterios con evidencia ({used_es}); el resto queda como no evaluable.",
                    f"The ranking uses only the criteria with evidence ({used_en}); the rest are reported as not evaluable.",
                ),
                (
                    "Lluvia satelital (GPM IMERG V07) con respaldo de NASA POWER; sin validación con estación local.",
                    "Satellite rainfall (GPM IMERG V07) backed up by NASA POWER; not validated with a local weather station.",
                ),
            ],
        )
    )

    # ------------------------------------------------------------------ zona y cobertura
    cov_items: list[tuple[str, str]] = []
    cov_table: ReportTable | None = None
    if coverage:
        partial = [c for c in coverage if int(c["n_valid"]) < int(c["n_expected"])]
        rows = []
        for c in coverage:
            valid, expected = int(c["n_valid"]), int(c["n_expected"])
            pct = 100.0 * valid / expected if expected else 0.0
            rows.append(
                [
                    str(c["year"]),
                    str(valid),
                    str(expected),
                    f"{pct:.1f}",
                    _bi(both, "Completo", "Complete")
                    if valid == expected
                    else _bi(
                        both,
                        f"PARCIAL: {expected - valid} días con NASA POWER",
                        f"PARTIAL: {expected - valid} days from NASA POWER",
                    ),
                ]
            )
        cov_table = ReportTable(
            caption_es="Cobertura de lluvia IMERG por año (días con dato IMERG / días del año)",
            caption_en="IMERG rainfall coverage per year (days with IMERG data / days in the year)",
            headers=[
                _bi(both, "Año", "Year"),
                _bi(both, "Días IMERG", "IMERG days"),
                _bi(both, "Días del año", "Days in year"),
                _bi(both, "Cobertura (%)", "Coverage (%)"),
                _bi(both, "Estado", "Status"),
            ],
            rows=rows,
            weights=[1, 1.2, 1.2, 1.3, 4],
        )
        window = (data_window or {}).get("imerg_window")
        for c in partial:
            year, valid, expected = c["year"], int(c["n_valid"]), int(c["n_expected"])
            until = f" (hasta {window[1]})" if isinstance(window, list) and len(window) == 2 else ""
            until_en = (
                f" (up to {window[1]})" if isinstance(window, list) and len(window) == 2 else ""
            )
            cov_items.append(
                (
                    f"El año {year} es PARCIAL para IMERG: {valid} de {expected} días con dato{until}. Los {expected - valid} días restantes usan lluvia de NASA POWER (otro producto, reanálisis); su total anual no es comparable con el de años completos.",
                    f"Year {year} is PARTIAL for IMERG: {valid} of {expected} days with data{until_en}. The remaining {expected - valid} days use NASA POWER rainfall (a different product, reanalysis); its annual total is not comparable with complete years.",
                )
            )
    else:
        primary = (data_window or {}).get("rain_primary") or "no registrada"
        cov_items.append(
            (
                f"No hay cobertura IMERG por año legible para esta zona (fuente primaria de lluvia declarada: {primary}): el informe no afirma una cobertura que no verificó.",
                f"No readable per-year IMERG coverage for this zone (declared primary rainfall source: {primary}): this report does not claim a coverage it did not verify.",
            )
        )
    sections.append(
        _section(
            both,
            "Zona, periodo y cobertura de datos",
            "Zone, period and data coverage",
            f"Zona: {zone_name}. Periodo: {period_text}. Cobertura = días con dato / días del año (denominador explícito).",
            f"Zone: {zone_name}. Period: {period_text}. Coverage = days with data / days in the year (explicit denominator).",
            cov_items,
            cov_table,
        )
    )

    # ------------------------------------------------------------------ estrategias y ciclos
    strat_rows = []
    for row in risk_rows:
        code = str(row["strategy"])
        full = [
            r
            for r in all_risk
            if r.get("strategy") == code and r.get("anchor_md") == row.get("anchor_md")
        ]
        cycles = full[0].get("by_cycle") or [] if full else []
        varieties = (
            ", ".join(sorted({str(c.get("variety")) for c in cycles if c.get("variety")})) or ND
        )
        strat_rows.append(
            [
                code.partition("_")[0],
                _bi(both, str(row.get("name", code)), _en(code, str(row.get("name", code)))),
                varieties,
                str(row.get("anchor_md") or ND),
                str(row.get("horizon_years") if row.get("horizon_years") is not None else ND),
                _bi(
                    both,
                    f"{row.get('n_decided', ND)} de {row.get('n_independent_cohorts', ND)}",
                    f"{row.get('n_decided', ND)} of {row.get('n_independent_cohorts', ND)}",
                ),
            ]
        )
    sections.append(
        _section(
            both,
            "Estrategias y ciclos evaluados",
            "Strategies and cycles evaluated",
            "Estrategias comparadas con su fecha de siembra de referencia, variedades de los ciclos y cohortes de años (decididas / independientes).",
            "Strategies compared with their reference planting date, the varieties of their cycles and the year cohorts (decided / independent).",
            table=ReportTable(
                caption_es="Estrategias, ciclos y cohortes",
                caption_en="Strategies, cycles and cohorts",
                headers=[
                    _bi(both, "Cód.", "Code"),
                    _bi(both, "Estrategia", "Strategy"),
                    _bi(both, "Variedades", "Varieties"),
                    _bi(both, "Siembra (MM-DD)", "Planting (MM-DD)"),
                    _bi(both, "Horizonte (años)", "Horizon (years)"),
                    _bi(
                        both,
                        "Cohortes decididas de independientes",
                        "Cohorts decided of independent",
                    ),
                ],
                rows=strat_rows,
                weights=[0.8, 3.6, 2.4, 1.3, 1.2, 1.7],
            ),
        )
    )

    # ------------------------------------------------------------------ riesgo
    risk_table_rows = []
    for row in risk_rows:
        code = str(row["strategy"])
        freq_v, freq_u, freq_ev = _ind(row.get("cohort_freq_critical"))
        water = row.get("water_inputs") or {}
        p90_v, p90_u, _ = _ind(water.get("p90_severity_by_agri_year"))
        tail_v, tail_u, _ = _ind(water.get("tail_ratio"))
        provisional = bool((row.get("cohort_freq_critical") or {}).get("provisional"))
        risk_table_rows.append(
            [
                _bi(both, str(row.get("name", code)), _en(code, str(row.get("name", code)))),
                f"{_n(freq_v)} {freq_u}".strip() if freq_v is not None else ND,
                f"{_n(p90_v)} {p90_u}".strip() if p90_v is not None else ND,
                f"{_n(tail_v, 2)} {tail_u}".strip() if tail_v is not None else ND,
                freq_ev,
                "Provisional (umbral sin cita) / Provisional (uncited threshold)"
                if provisional
                else "—",
            ]
        )
    sections.append(
        _section(
            both,
            "Riesgo por estrategia",
            "Risk by strategy",
            f"Indicador de exposición climática por estrategia en la fecha de siembra de referencia; escenario {scenario_id}. No es déficit real de agua del suelo.",
            f"Climate-exposure indicator per strategy at the reference planting date; scenario {scenario_id}. It is not an actual soil water deficit.",
            table=ReportTable(
                caption_es="Frecuencia de cohortes críticas (%), severidad P90 (mm) y razón de cola",
                caption_en="Critical-cohort frequency (%), P90 severity (mm) and tail ratio",
                headers=[
                    _bi(both, "Estrategia", "Strategy"),
                    _bi(both, "Frec. cohortes críticas", "Critical-cohort freq."),
                    _bi(both, "Severidad P90", "P90 severity"),
                    _bi(both, "Razón de cola", "Tail ratio"),
                    "Ev.",
                    _bi(both, "Estado", "Status"),
                ],
                rows=risk_table_rows,
                weights=[3.3, 1.5, 1.4, 1.3, 0.6, 2.6],
            ),
        )
    )

    # ------------------------------------------------------------------ ranking y criterios
    if rank and rank.get("ranking"):
        stab = rank.get("stability") or {}
        rank_rows = []
        for r in rank["ranking"]:
            crit = r.get("criteria") or {}
            cells = []
            for crit_code in CRITERIA:
                cv = crit.get(crit_code) or {}
                if cv.get("status") == "not_evaluable" or cv.get("value") is None:
                    cells.append("no evaluable / not evaluable")
                else:
                    cells.append(f"{_n(cv.get('value'), 2)} ({cv.get('evidence') or '—'})")
            code = str(r["strategy"])
            name = next((str(x.get("name")) for x in risk_rows if x.get("strategy") == code), code)
            rank_rows.append(
                [str(r["rank"]), _bi(both, name, _en(code, name)), _n(r.get("total"), 2), *cells]
            )
        sections.append(
            _section(
                both,
                "Comparación de estrategias",
                "Strategy comparison",
                f"Ranking sobre los criterios evaluables ({used_es}). Estabilidad del orden ante pesos distintos: {stab.get('flag')}. La estabilidad no es la probabilidad de que una estrategia sea la mejor.",
                f"Ranking over the evaluable criteria only ({used_en}). Stability of the order under changed weights: {stab.get('flag')}. Stability is not the probability that a strategy is best.",
                [
                    (
                        f"Muestras de estabilidad: {stab.get('n_samples', ND)}, semilla {stab.get('seed', ND)}, modo {stab.get('mode', ND)}; correlación de rangos media {_n(stab.get('rank_corr_mean'), 2)}.",
                        f"Stability samples: {stab.get('n_samples', ND)}, seed {stab.get('seed', ND)}, mode {stab.get('mode', ND)}; mean rank correlation {_n(stab.get('rank_corr_mean'), 2)}.",
                    ),
                    (
                        f"Margen entre la primera y la segunda: {_n(rank.get('top_margin'), 2)} (índice 0\u20131); dentro de la incertidumbre: {'sí' if rank.get('margin_within_uncertainty') else 'no'}.",
                        f"Margin between first and second: {_n(rank.get('top_margin'), 2)} (index 0\u20131); within uncertainty: {'yes' if rank.get('margin_within_uncertainty') else 'no'}.",
                    ),
                ],
                ReportTable(
                    caption_es="Puntaje total y valor por criterio (índice 0\u20131; entre paréntesis, nivel de evidencia)",
                    caption_en="Total score and value per criterion (index 0\u20131; evidence level in brackets)",
                    headers=[
                        "#",
                        _bi(both, "Estrategia", "Strategy"),
                        _bi(both, "Total", "Total"),
                        _bi(both, "Agua", "Water"),
                        _bi(both, "Suelo", "Soil"),
                        _bi(both, "Alimento", "Food"),
                        _bi(both, "Ingreso", "Income"),
                    ],
                    rows=rank_rows,
                    weights=[0.4, 3.2, 0.9, 1.5, 1.5, 1.7, 1.7],
                ),
            )
        )
        weights = rank.get("weights") or {}
        effective = rank.get("weights_effective") or {}
        first_criteria = (rank["ranking"][0].get("criteria") or {}) if rank["ranking"] else {}
        crit_rows = []
        for crit_code, (es_name, en_name) in CRITERIA.items():
            cv = first_criteria.get(crit_code) or {}
            reason = str(cv.get("reason") or "—")
            crit_rows.append(
                [
                    _bi(both, es_name, en_name),
                    _n(weights.get(crit_code), 2),
                    _n(effective.get(crit_code), 2)
                    if crit_code in effective
                    else "0 (excluido / excluded)",
                    _bi(both, *STATUS_LABEL.get(str(cv.get("status")), (ND, ND))),
                    _reason_text(reason, both),
                ]
            )
        sections.append(
            _section(
                both,
                "Criterios efectivamente usados",
                "Criteria effectively used",
                "Pesos solicitados y aplicados tras excluir los criterios sin evidencia; el motivo viene del motor.",
                "Weights requested and applied after excluding the criteria without evidence; the reason comes from the engine.",
                [
                    (
                        f"Cobertura de pesos: {_n(rank.get('weight_coverage'), 2)} (fracción del peso solicitado que sí tiene evidencia).",
                        f"Weight coverage: {_n(rank.get('weight_coverage'), 2)} (fraction of the requested weight that has evidence).",
                    )
                ],
                ReportTable(
                    caption_es="Criterios del ranking",
                    caption_en="Ranking criteria",
                    headers=[
                        _bi(both, "Criterio", "Criterion"),
                        _bi(both, "Peso solicitado", "Weight requested"),
                        _bi(both, "Peso aplicado", "Weight applied"),
                        _bi(both, "Estado", "Status"),
                        _bi(both, "Motivo", "Reason"),
                    ],
                    rows=crit_rows,
                    weights=[1.8, 1.2, 1.4, 1.3, 4.2],
                ),
            )
        )

    # ------------------------------------------------------------------ escenarios
    if scenarios:
        sc_rows = []
        for item in scenarios:
            row = item["scenario"]
            sc_rows.append(
                [
                    str(row.get("scenario_id")),
                    _n(row.get("delta_t_c"), 1),
                    _n(row.get("precip_factor"), 2),
                    str(row.get("onset_delay_days", ND)),
                    str(row.get("humidity_assumption", ND)),
                    str(row.get("adaptation_mode", ND)),
                ]
            )
        cmp_rows = []
        for strat in risk_rows:
            code = str(strat["strategy"])
            name = str(strat.get("name", code))
            cells = []
            for item in scenarios:
                srow = next(
                    (r for r in item.get("risk_rows", []) if r.get("strategy") == code), None
                )
                v, u, _ = _ind((srow or {}).get("cohort_freq_critical"))
                cells.append(f"{_n(v)} {u}".strip() if v is not None else ND)
            cmp_rows.append([_bi(both, name, _en(code, name)), *cells])
        sc_items = [
            (
                "Los escenarios son perturbaciones sintéticas y deterministas de la serie histórica; no son pronósticos ni proyecciones CMIP6.",
                "Scenarios are synthetic, deterministic perturbations of the historical series; they are not forecasts or CMIP6 projections.",
            )
        ]
        tables_ok = len(scenarios) <= 5
        sections.append(
            _section(
                both,
                "Escenarios sintéticos calculados",
                "Synthetic scenarios computed",
                "Escenarios hipotéticos ya calculados para esta corrida, comparados con la serie histórica (BASE).",
                "Hypothetical scenarios already computed for this run, compared with the historical series (BASE).",
                sc_items,
                ReportTable(
                    caption_es="Parámetros de cada escenario",
                    caption_en="Parameters of each scenario",
                    headers=[
                        _bi(both, "Escenario", "Scenario"),
                        "ΔT (°C)",
                        _bi(both, "Factor de lluvia (\u00d7)", "Rainfall factor (\u00d7)"),
                        _bi(both, "Retraso inicio (días)", "Onset delay (days)"),
                        _bi(both, "Humedad", "Humidity"),
                        _bi(both, "Adaptación", "Adaptation"),
                    ],
                    rows=sc_rows,
                    weights=[3, 1, 1.4, 1.4, 1.6, 1.4],
                ),
            )
        )
        if tables_ok:
            sections.append(
                _section(
                    both,
                    "Frecuencia de cohortes críticas por escenario",
                    "Critical-cohort frequency by scenario",
                    "Misma métrica que «Riesgo por estrategia», recalculada por el motor en cada escenario (%).",
                    "Same metric as «Risk by strategy», recomputed by the engine for each scenario (%).",
                    table=ReportTable(
                        caption_es="Frecuencia de cohortes críticas (%) por escenario",
                        caption_en="Critical-cohort frequency (%) by scenario",
                        headers=[
                            _bi(both, "Estrategia", "Strategy"),
                            *[str(item["scenario"].get("scenario_id")) for item in scenarios],
                        ],
                        rows=cmp_rows,
                    ),
                )
            )
    else:
        sections.append(
            _section(
                both,
                "Escenarios sintéticos",
                "Synthetic scenarios",
                "Este informe usa solo la serie histórica (BASE): no hay escenarios sintéticos calculados para esta corrida.",
                "This report uses the historical series only (BASE): no synthetic scenarios have been computed for this run.",
            )
        )

    # ------------------------------------------------------------------ indicadores y procedencia
    prov_rows: list[list[str]] = []
    not_recorded: list[frozenset[str]] = []
    seen: set[str] = set()

    def add_indicator(ind: Any) -> None:
        if not isinstance(ind, Mapping) or str(ind.get("code")) in seen:
            return
        seen.add(str(ind.get("code")))
        prov = ind.get("provenance") or {}
        kind_es, kind_en = _provenance_label(ind)
        spatial = prov.get("spatial_res")
        temporal = prov.get("temporal_res")
        resolution = (
            " · ".join(str(x) for x in (spatial, temporal) if x)
            + ("" if spatial and temporal else " (el resto no registrado / the rest not recorded)")
            if (spatial or temporal)
            else "no registrada por el motor / not recorded by the engine"
        )
        lim = "; ".join(str(x) for x in (prov.get("limitations") or [])[:2]) or "—"
        _, unit, evidence = _ind(ind)
        label_es = INDICATOR_LABEL_ES.get(
            str(ind.get("code")), str(ind.get("label_es") or ind.get("code"))
        )
        prov_rows.append(
            [
                f"{label_es} ({unit})" if unit else label_es,
                _bi(both, kind_es, kind_en),
                evidence,
                _source_text(prov),
                resolution,
                _cut(f"{prov.get('method') or ND}. {lim}", 280),
            ]
        )
        not_recorded.append(_not_recorded(prov))

    if risk_rows:
        first = risk_rows[0]
        add_indicator(first.get("cohort_freq_critical"))
        for ind in (first.get("water_inputs") or {}).values():
            add_indicator(ind)
    if climate:
        years = climate.get("years") or []
        if years:
            add_indicator(years[-1].get("precip_mm"))
            add_indicator(years[-1].get("et0_mm"))
    sections.append(
        _section(
            both,
            "Indicadores y procedencia",
            "Indicators and provenance",
            "Para cada indicador: tipo de evidencia, nivel (A/B/C), fuente e institución, resolución, método y lo que el motor NO registró (se indica en lugar de rellenarlo).",
            "For each indicator: evidence type, level (A/B/C), source and institution, resolution, method and what the engine did NOT record (stated instead of filled in).",
            [
                (
                    "Tipos de evidencia: observado/medido, satélite o reanálisis, derivado/modelado, declarado, hipotético (escenario sintético) y no disponible.",
                    "Evidence types: observed/measured, satellite or reanalysis, derived/modelled, declared, hypothetical (synthetic scenario) and not available.",
                ),
                *_not_recorded_items(not_recorded),
            ],
            ReportTable(
                caption_es="Procedencia de los indicadores",
                caption_en="Provenance of the indicators",
                headers=[
                    _bi(both, "Indicador", "Indicator"),
                    _bi(both, "Tipo", "Type"),
                    "Ev.",
                    _bi(both, "Fuente e institución", "Source and institution"),
                    _bi(
                        both, "Resolución (espacial · temporal)", "Resolution (spatial · temporal)"
                    ),
                    _bi(both, "Método y límites", "Method and limits"),
                ],
                rows=prov_rows,
                weights=[2.2, 1.5, 0.6, 2.4, 1.5, 4.2],
            )
            if prov_rows
            else None,
        )
    )

    # ------------------------------------------------------------------ decisiones pendientes
    pend_rows: list[list[str]] = []
    for entry in decision_log:
        if not isinstance(entry, Mapping):
            continue
        code = str(entry.get("decision"))
        if code == "fecha_ancla_para_ranking":
            anchors = entry.get("anchors") or {}
            listing = "; ".join(f"{k.split('_')[0]} {v}" for k, v in anchors.items())
            pend_rows.append(
                [
                    _bi(
                        both,
                        "Fecha de siembra usada en el ranking",
                        "Planting date used in the ranking",
                    ),
                    "—",
                    _bi(
                        both,
                        f"Política «{entry.get('policy')}» (inicio de la ventana de cada estrategia): {listing}",
                        f"Policy «{entry.get('policy')}» (start of each strategy's window): {listing}",
                    ),
                ]
            )
            continue
        es_name, en_name, es_note, en_note = DECISIONS.get(
            code, (code, code, str(entry.get("note") or ""), str(entry.get("note") or ""))
        )
        subject = str(entry.get("criterion") or entry.get("strategy") or "")
        if subject in CRITERIA:
            subject = _bi(both, CRITERIA[subject][0], CRITERIA[subject][1])
        pend_rows.append([_bi(both, es_name, en_name), subject or "—", _bi(both, es_note, en_note)])
    if isinstance(voi, Mapping):
        outcome = str(voi.get("outcome"))
        pend_rows.append(
            [
                _bi(
                    both, "Valor de la información del pH del suelo", "Value of soil-pH information"
                ),
                str(voi.get("property_code") or "ph"),
                _bi(
                    both,
                    f"Resultado: {outcome}. {voi.get('rationale_es') or ''}".strip(),
                    f"Outcome: {outcome}. No documented, cited pH range for the crops, so the engine cannot say whether a lab test would change the order."
                    if outcome == "insufficient_info"
                    else f"Outcome: {outcome}.",
                ),
            ]
        )
    sections.append(
        _section(
            both,
            "Decisiones pendientes",
            "Pending decisions",
            "Decisiones que el motor no pudo tomar y que siguen siendo humanas.",
            "Decisions the engine could not take and that remain human ones.",
            [
                (
                    "Qué sembrar, cuándo y con qué prioridades sigue siendo una decisión de la persona técnica y de la familia agricultora.",
                    "What to plant, when and with which priorities remains a decision for the technician and the farming household.",
                )
            ],
            ReportTable(
                caption_es="Registro de decisiones del ranking y de la información de suelo",
                caption_en="Ranking decision log and soil information",
                headers=[
                    _bi(both, "Decisión", "Decision"),
                    _bi(both, "Sobre", "About"),
                    _bi(both, "Detalle", "Detail"),
                ],
                rows=pend_rows,
                weights=[3, 1.6, 4.4],
            )
            if pend_rows
            else None,
        )
    )

    # ------------------------------------------------------------------ datos faltantes
    sections.append(
        _section(
            both,
            "Datos faltantes y qué obtener",
            "Missing data and what to obtain next",
            "Lo que falta y qué información adicional cambiaría lo que el motor puede afirmar.",
            "What is missing and which additional information would change what the engine can say.",
            [
                (
                    "Propiedades del suelo (pH, materia orgánica, capacidad de agua disponible, profundidad efectiva): no medidas ni declaradas, por lo que no se calcula el balance hídrico de la zona radicular.",
                    "Soil properties (pH, organic matter, available water capacity, effective depth): not measured or declared, so the root-zone water balance is not run.",
                ),
                (
                    "Un análisis de pH en laboratorio permitiría evaluar la compatibilidad cultivo-pH y el valor de esa información.",
                    "A laboratory pH analysis would let the engine evaluate crop-pH compatibility and the value of that information.",
                ),
                (
                    "Rendimientos de referencia, precios y composición de alimentos con cita para cada cultivo: necesarios para los criterios de alimento e ingreso.",
                    "Cited reference yields, prices and food composition for each crop: needed to evaluate the food and income criteria.",
                ),
                (
                    "Umbrales de etapa crítica y coeficientes de cultivo con cita: hasta entonces todo resultado basado en umbrales es provisional.",
                    "Cited critical-stage thresholds and crop coefficients: until then every threshold-based result is provisional.",
                ),
                (
                    "Una estación meteorológica local para validar la lluvia satelital (evidencia C hasta entonces).",
                    "A local weather station to validate the satellite rainfall (evidence level C until then).",
                ),
            ]
            + (
                [
                    (
                        "Criterios sin evidencia en este informe: "
                        + ", ".join(CRITERIA[c][0] for c in missing_criteria)
                        + ".",
                        "Criteria without evidence in this report: "
                        + ", ".join(CRITERIA[c][1] for c in missing_criteria)
                        + ".",
                    )
                ]
                if missing_criteria
                else []
            ),
        )
    )
    sections.append(
        _section(
            both,
            "Condiciones a validar en campo",
            "Conditions to validate in the field",
            "Supuestos del modo de prueba que deben confirmarse localmente antes de decidir.",
            "Sandbox assumptions that must be confirmed locally before any decision.",
            [
                (
                    "Ventanas de siembra e inicio del año agrícola con técnicos locales.",
                    "Planting windows and the start of the agricultural year with local technicians.",
                ),
                (
                    "Duración del ciclo y etapas críticas de las variedades realmente usadas.",
                    "Cycle length and critical stages of the varieties actually used.",
                ),
                (
                    "Si la definición de inicio de lluvias usada en los escenarios de retraso coincide con la práctica local.",
                    "Whether the rain-onset definition used for delay scenarios matches local practice.",
                ),
                (
                    "Que el polígono piloto sea representativo de las fincas asesoradas.",
                    "That the pilot polygon is representative of the farms being advised.",
                ),
            ],
        )
    )

    # ------------------------------------------------------------------ anexo
    annex = [
        _section(
            both,
            "Modo de cálculo",
            "Why this calculation mode",
            f"El motor usó {mode_es} porque faltan o no están declarados los datos listados.",
            f"The engine used {mode_en} because the following are missing or not declared.",
            [_mode_reason(r) for r in reasons][:60],
        ),
        _section(
            both,
            "Fuentes y procesamiento",
            "Sources and processing",
            "Fuentes de datos, institución y procesamiento tal como quedaron registrados con la corrida.",
            "Data sources, institution and processing, as recorded with the run.",
            [
                (
                    "NASA POWER diario (MERRA-2 / CERES), comunidad AG: temperatura, humedad, viento, radiación y lluvia de respaldo. Institución: NASA. Resolución ~0.5° \u00d7 0.625°.",
                    "NASA POWER daily (MERRA-2 / CERES), community AG: temperature, humidity, wind, radiation and fallback rainfall. Institution: NASA. Resolution ~0.5° \u00d7 0.625°.",
                ),
                (
                    "GPM IMERG diario V07B (GES DISC, DOI 10.25966/564j-4331): lluvia primaria a 0.1°. Institución: NASA. Sin validación con estación local.",
                    "GPM IMERG daily V07B (GES DISC, DOI 10.25966/564j-4331): primary rainfall at 0.1°. Institution: NASA. Not validated with a local station.",
                ),
                (
                    "ET0 por el método FAO-56 (calculada por el motor) con variables de POWER y presión de vapor desde el punto de rocío; lluvia efectiva por década con tres métodos.",
                    "ET0 by the FAO-56 reference method (computed by the engine) from POWER variables with the dew-point vapour-pressure route; effective rainfall by dekad with three methods.",
                ),
                (
                    "Los escenarios sintéticos son perturbaciones deterministas de la serie histórica; no son pronósticos ni proyecciones CMIP6.",
                    "Synthetic scenarios are deterministic perturbations of the historical series; they are not forecasts or CMIP6 projections.",
                ),
            ],
        ),
    ]
    when = now or datetime.now(UTC)
    return ReportInput(
        locale="es+en" if both else "es",
        privacy_level="public" if privacy_level == "public" else "internal",
        zone_name=zone_name[:300],
        run_id=run_id,
        hashes=hashes,
        generated_at=when,
        summary_es=_cut(
            f"Comparación de {n_strat} estrategias en la zona {zone_name} (modo {mode_es}). Resultado provisional: umbrales y catálogos en modo sandbox, evidencia C.",
            8000,
        ),
        summary_en=_cut(
            f"Comparison of {n_strat} strategies for zone {zone_name} (mode {mode_en}). Provisional result: thresholds and catalogs are in sandbox mode, evidence level C. "
            "This report is not an automatic recommendation and not a yield estimate.",
            8000,
        )
        if both
        else None,
        sections=sections,
        annex=annex,
        assumptions=[],
        limitations=[_cut(x) for x in limitations]
        or [
            "Catálogos y umbrales sandbox: no usar para decidir. / Sandbox catalogs and thresholds: do not use for decisions."
        ],
        references=[
            ReferenceItem(
                text="Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). Crop evapotranspiration: guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56.",
                product_version=None,
            ),
            ReferenceItem(
                text="NASA Langley Research Center. Prediction Of Worldwide Energy Resources (POWER), daily data, community AG. https://power.larc.nasa.gov/",
                product_version="daily",
            ),
            ReferenceItem(
                text="NASA GES DISC. GPM IMERG daily GIS product (DOI 10.25966/564j-4331).",
                product_version="V07B",
            ),
        ],
        provenance_notes=[
            "Serie diaria NASA POWER y lluvia GPM IMERG donde existe; nivel de evidencia por cifra tal como lo informa el motor. / NASA POWER daily series and GPM IMERG rainfall where available; evidence level per figure as reported by the engine."
        ],
        provisional_banner=True,
    )
