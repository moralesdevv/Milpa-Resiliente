"""E/S para ``milpa_core`` (R2): region pack, catálogos, estrategias y serie curada de R1.

El núcleo científico no lee archivos (README §10). Este módulo hace SOLO lectura y conversión de
formato hacia los objetos tipados de ``milpa_core``; no calcula nada científico. Procede de
``tools/r2/milpa_adapter.py`` (entregado por R2) y se mantiene equivalente.

Contrato R1↔R2 (verificado contra el ``daily.parquet`` real de R1): la serie curada no trae
``cell_id`` y ``obs_date`` es un timestamp; ambos casos están tolerados. Los días ausentes se
representan como NaN, nunca como cero.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from milpa_core.climate.series import ClimateSeries, default_met_prov, default_precip_prov
from milpa_core.config import (
    OnsetDef,
    RankingConfig,
    RegionConfig,
    Season,
    SoilCriterionConfig,
    StabilityConfig,
    VoiConfig,
)
from milpa_core.crops import Catalogs, Crop, PhTolerance, Stage, Threshold, Variety
from milpa_core.enums import (
    Criterion,
    Evidence,
    PeffMethod,
    QcFlag,
    StrategyAxis,
    ThresholdMetric,
    WindowMode,
)
from milpa_core.strategy import Component, Strategy, StrategyCycle

DAILY_COLS = [
    "tmax_c",
    "tmin_c",
    "tdew_c",
    "rh_pct",
    "wind2m_ms",
    "srad_mj_m2",
    "precip_mm",
    "qc_flags",
]
REQUIRED = ["tmax_c", "tmin_c", "precip_mm", "wind2m_ms", "srad_mj_m2"]

# Alias aceptados (minúsculas); el primero que exista gana.
ALIASES: dict[str, list[str]] = {
    "obs_date": [
        "obs_date",
        "date",
        "fecha",
        "day",
        "dia",
        "time",
        "datetime",
        "yyyymmdd",
        "obs_day",
        "dt",
    ],
    "cell_id": ["cell_id", "cell", "celda", "grid_id", "pixel_id", "zone_cell"],
    "tmax_c": ["tmax_c", "tmax", "t2m_max", "temp_max", "tmax_degc", "t_max"],
    "tmin_c": ["tmin_c", "tmin", "t2m_min", "temp_min", "tmin_degc", "t_min"],
    "tdew_c": ["tdew_c", "tdew", "t2mdew", "dewpoint", "td", "t_dew", "dew_point_c"],
    "rh_pct": ["rh_pct", "rh", "rh2m", "humidity", "hr", "rh_mean"],
    "wind2m_ms": ["wind2m_ms", "ws2m", "wind2m", "wind", "u2", "wind_ms", "ws2m_ms"],
    "srad_mj_m2": [
        "srad_mj_m2",
        "allsky_sfc_sw_dwn",
        "srad",
        "rs",
        "rs_mj_m2",
        "solar_rad",
        "radiation",
    ],
    "precip_mm": [
        "precip_mm",
        "precip",
        "precipitation",
        "prcp",
        "p_mm",
        "rain",
        "rain_mm",
        "lluvia",
        "imerg_mm",
        "precip_imerg",
        "imerg",
        "precipitation_mm",
        "prectotcorr",
        "p",
    ],
    "qc_flags": ["qc_flags", "qc", "flags", "qc_flag"],
    "et0_mm": ["et0_mm", "et0", "eto"],
}


@dataclass(frozen=True)
class RegionExtras:
    """Configuración del region pack que no forma parte de ``RegionConfig``."""

    crops_enabled: tuple[str, ...] | None
    ranking_cfg: RankingConfig
    stability_cfg: StabilityConfig
    voi_cfg: VoiConfig
    soil_cfg: SoilCriterionConfig
    cell_id: str | None
    region_hash: str


@dataclass(frozen=True)
class CuratedInfo:
    """Metadatos de la lectura de la serie curada (trazabilidad; sin efectos secundarios)."""

    cell_id: str
    n_days: int
    fallback_share: float
    column_mapping: dict[str, str]
    missing_pct: dict[str, float]
    notes: list[str] = field(default_factory=list)
    r1_et0_mm: np.ndarray[Any, Any] | None = None


def _yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _evidence(value: Any, default: Evidence = Evidence.C) -> Evidence:
    return Evidence(value) if value else default


def load_region(path: str | Path) -> tuple[RegionConfig, RegionExtras]:
    path = Path(path)
    d = _yaml(path)
    z = d["zone"]
    seasons = {
        s["code"]: Season(s["code"], int(s["calendar_year_shift"]), tuple(s["plant_window"]))
        for s in d["seasons"]
    }
    on = d.get("onset") or {}
    onset = (
        OnsetDef(
            on["search_start_md"],
            float(on["x_mm"]),
            int(on["n_days"]),
            int(on["y_days"]),
            int(on["z_days"]),
            float(on.get("dry_day_mm", 1.0)),
            on.get("citation"),
        )
        if on.get("search_start_md")
        else None
    )
    ad = d.get("adaptation") or {}
    pr = d["precip"]
    qc = d["qc"]
    win = d["window"]
    region = RegionConfig(
        code=d["region"],
        status=d["status"],
        lat_deg=float(z["lat_deg"]),
        elevation_m=float(z["elevation_m"]),
        window_start=str(win["start"]),
        window_end=str(win["end"]),
        seasons=seasons,
        agri_year_start=str(d["agri_year_start"]),
        min_valid_years=int(win["min_valid_years"]),
        step_days=int(d["planting_candidates"]["step_days"]),
        primary_peff=PeffMethod(pr["primary_peff"]),
        peff_enabled=tuple(PeffMethod(m) for m in pr["peff_enabled"]),
        phi=pr.get("phi"),
        max_missing_precip_pct=float(qc["max_missing_precip_pct"]),
        max_missing_met_pct=float(qc["max_missing_met_pct"]),
        ea_sensitivity_tol_pct=d["et0"].get("ea_sensitivity_tol_pct"),
        onset=onset,
        adaptation_lag_days=ad.get("lag_days"),
        adaptation_citation=ad.get("citation"),
        priorities_default={Criterion(k): float(v) for k, v in d["priorities_default"].items()},
        communication_tol_pct=float(d.get("communication_tol_pct", 10)),
        min_segment_days=int(d.get("min_segment_days", 1)),
    )
    voi = d["voi"]
    extras = RegionExtras(
        crops_enabled=tuple(d.get("crops_enabled") or ()) or None,
        ranking_cfg=RankingConfig(
            min_weight_coverage=float(d["ranking"]["min_weight_coverage"]),
            missing_policy=d["ranking"]["missing_policy"],
        ),
        stability_cfg=StabilityConfig(**dict(d["stability"].items())),
        voi_cfg=VoiConfig(
            n_hyp=voi["n_hyp"],
            top_k=voi["top_k"],
            zone_ph_range=tuple(voi["zone_ph_range"]) if voi.get("zone_ph_range") else None,
            zone_ph_range_citation=voi.get("zone_ph_range_citation"),
        ),
        soil_cfg=SoilCriterionConfig(
            float((d.get("soil_criterion") or {}).get("min_subindicator_coverage", 0.5))
        ),
        cell_id=z.get("cell_id"),
        region_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    return region, extras


def load_catalogs(dirpath: str | Path, mode: str = "sandbox") -> Catalogs:
    base = Path(dirpath)
    c = _yaml(base / "crops.yaml")
    crops = {
        x["code"]: Crop(
            x["code"],
            x["name_es"],
            x["family"],
            bool(x.get("is_legume")),
            x.get("fixes_n_conditions"),
            x.get("residue_return"),
            x.get("residue_citation"),
        )
        for x in c["crops"]
    }
    varieties: dict[str, Variety] = {}
    for v in c["varieties"]:
        stages = tuple(
            Stage(
                s["code"],
                int(s["seq"]),
                float(s["kc_start"]),
                float(s["kc_end"]),
                bool(s.get("critical")),
                s.get("length_days"),
                s.get("gdd_start"),
                s.get("gdd_end"),
                s.get("citation"),
                _evidence(s.get("evidence"), Evidence.B if s.get("citation") else Evidence.C),
            )
            for s in v["stages"]
        )
        rd = v.get("root_depth") or {}
        dp = v.get("depletion_fraction_p") or {}
        varieties[v["code"]] = Variety(
            v["code"],
            v["crop"],
            v.get("name", v["code"]),
            v["phenology_basis"],
            stages,
            crops[v["crop"]].family,
            v.get("gdd_base_c"),
            rd.get("z_min_m"),
            rd.get("z_max_m"),
            dp.get("value"),
            rd.get("citation"),
            dp.get("citation"),
            v.get("fallow_kc"),
            v.get("fallow_kc_citation"),
            v.get("citation"),
        )
    t = _yaml(base / "thresholds.yaml")
    thresholds = tuple(
        Threshold(
            x["crop"],
            x["stage"],
            ThresholdMetric(x["metric"]),
            x.get("value"),
            x.get("sens_low"),
            x.get("sens_high"),
            PeffMethod(x["peff_method"]) if x.get("peff_method") else None,
            unit=x.get("unit", "mm"),
            evidence=_evidence(x.get("evidence")),
            citation=x.get("citation"),
        )
        for x in t["thresholds"]
    )
    ph_file = base / "ph_tolerance.yaml"
    p = _yaml(ph_file) if ph_file.exists() else {}
    ph_tol = {
        x["crop"]: PhTolerance(
            x["crop"],
            x["ph_abs_min"],
            x["ph_opt_min"],
            x["ph_opt_max"],
            x["ph_abs_max"],
            x["ph_method"],
            _evidence(x.get("evidence")),
            x["citation"],
        )
        for x in (p.get("ph_tolerance") or [])
    }
    ref_yields = {
        x["variety"]: (float(x["kg_ha"]), _evidence(x.get("evidence")), x["citation"])
        for x in (p.get("reference_yields") or [])
    }
    food = {
        x["crop"]: (float(x["kcal_per_kg"]), float(x["protein_g_per_kg"]), x["citation"])
        for x in (p.get("food_composition") or [])
    }
    prices = {
        x["crop"]: (float(x["price_per_kg"]), x["currency"], str(x["date"]), x["source"])
        for x in (p.get("prices") or [])
    }
    costs = {
        x["crop"]: (float(x["cost_ha"]), x["currency"], str(x["date"]), x["source"])
        for x in (p.get("variable_costs") or [])
    }
    digest = hashlib.sha256()
    for f in sorted(base.glob("*.yaml")):
        digest.update(f.read_bytes())
    return Catalogs(
        crops,
        varieties,
        thresholds,
        ph_tol,
        ref_yields,
        food,
        prices,
        costs,
        digest.hexdigest(),
        mode,
    )


def load_strategies(path: str | Path) -> list[Strategy]:
    out: list[Strategy] = []
    for s in _yaml(Path(path)):
        cycles = []
        for c in s["cycles"]:
            comps = tuple(
                Component(
                    x["variety"],
                    x.get("role", "principal"),
                    float(x.get("area_fraction", 1.0)),
                    int(x.get("plant_offset_days", 0)),
                )
                for x in c["components"]
            )
            cycles.append(
                StrategyCycle(
                    int(c["cycle_idx"]),
                    c["season"],
                    comps,
                    WindowMode(c["window_mode"]),
                    int(c.get("agri_year_offset", 0)),
                    tuple(c["plant_window"]) if c.get("plant_window") else None,
                    int(c.get("rel_lag_days", 0)),
                    int(c.get("fallow_after_days", 0)),
                    bool(c.get("soil_carryover", False)),
                )
            )
        out.append(
            Strategy(
                s["code"],
                s["name"],
                tuple(cycles),
                int(s.get("version", 1)),
                tuple(StrategyAxis(a) for a in s.get("changes_from_reference", [])),
                bool(s.get("is_reference", False)),
                int(s.get("anchor_cycle_idx", 1)),
            )
        )
    return out


def _normalise_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Renombra las columnas de R1 al contrato del motor; devuelve el mapeo usado."""
    if df.index.name is not None or isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
    lower = {str(c).lower().strip(): str(c) for c in df.columns}
    mapping: dict[str, str] = {}
    for target, names in ALIASES.items():
        for n in names:
            if n in lower and lower[n] not in mapping.values():
                mapping[target] = lower[n]
                break
    if "obs_date" not in mapping and {"year", "month", "day"} <= set(lower):
        df["__date"] = pd.to_datetime(
            {"year": df[lower["year"]], "month": df[lower["month"]], "day": df[lower["day"]]}
        )
        mapping["obs_date"] = "__date"
    if "obs_date" not in mapping and {"year", "doy"} <= set(lower):
        df["__date"] = pd.to_datetime(
            df[lower["year"]].astype(int).astype(str)
            + df[lower["doy"]].astype(int).astype(str).str.zfill(3),
            format="%Y%j",
        )
        mapping["obs_date"] = "__date"
    df = df.rename(columns={v: k for k, v in mapping.items()})
    missing = [c for c in ["obs_date", *REQUIRED] if c not in df.columns]
    if missing:
        raise KeyError(
            f"Faltan columnas {missing} en la serie curada. Columnas encontradas: "
            f"{list(lower.values())}"
        )
    return df, mapping


def load_curated_daily(
    path: str | Path,
    cell_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[ClimateSeries, CuratedInfo]:
    """Lee ``curated/<zona>/daily.parquet`` (o CSV) de R1 → ``ClimateSeries`` continua.

    Los días ausentes quedan como NaN (nunca cero). No se rellena ningún dato.
    """
    path = Path(path)
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    df, mapping = _normalise_columns(df)
    if "cell_id" in df.columns:
        cells = sorted(df["cell_id"].astype(str).unique())
        cid = str(cell_id) if cell_id is not None else cells[0]
        df = df[df["cell_id"].astype(str) == cid]
    else:
        cid = "cell"
    d = df["obs_date"]
    if pd.api.types.is_numeric_dtype(d):  # 20210101
        d = pd.to_datetime(d.astype(int).astype(str), format="%Y%m%d")
    dt = pd.to_datetime(d)
    if dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
    df["obs_date"] = dt.dt.normalize()
    df = df.sort_values("obs_date").drop_duplicates("obs_date").set_index("obs_date")
    for c in [
        "tmax_c",
        "tmin_c",
        "tdew_c",
        "rh_pct",
        "wind2m_ms",
        "srad_mj_m2",
        "precip_mm",
        "et0_mm",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df.loc[df[c] <= -900, c] = np.nan  # centinela -999 de POWER
    notes: list[str] = []
    if "srad_mj_m2" in df.columns and df["srad_mj_m2"].median() < 10:
        df["srad_mj_m2"] = df["srad_mj_m2"] * 3.6  # POWER comunidad RE: kWh m-2 d-1
        notes.append("srad convertida de kWh/m²/d a MJ/m²/d (factor 3.6)")
    if "rh_pct" in df.columns and df["rh_pct"].max() <= 1.0:
        df["rh_pct"] = df["rh_pct"] * 100
        notes.append("RH convertida de fracción a %")
    first = pd.Timestamp(start) if start else df.index.min()
    last = pd.Timestamp(end) if end else df.index.max()
    df = df.reindex(pd.date_range(first, last, freq="D"))  # días ausentes → NaN
    for c in DAILY_COLS:
        if c not in df.columns:
            df[c] = np.nan
    if "qc_flags" in mapping:
        qc = df["qc_flags"].fillna(QcFlag.MISSING).astype(int).to_numpy()
    else:
        qc = np.where(df["precip_mm"].isna(), QcFlag.MISSING, 0).astype(int)
    fallback_share = float(np.mean((qc & QcFlag.FALLBACK_SOURCE) > 0))
    precip_prov = default_precip_prov()
    if fallback_share > 0:
        precip_prov = replace(
            precip_prov,
            limitations=(
                *precip_prov.limitations,
                f"{fallback_share:.1%} de días con fuente de respaldo (POWER)",
            ),
        )
    series = ClimateSeries(
        dates=df.index.values.astype("datetime64[D]"),
        tmax_c=df["tmax_c"].to_numpy(float),
        tmin_c=df["tmin_c"].to_numpy(float),
        precip_mm=df["precip_mm"].to_numpy(float),
        wind2m_ms=df["wind2m_ms"].to_numpy(float),
        srad_mj_m2=df["srad_mj_m2"].to_numpy(float),
        tdew_c=df["tdew_c"].to_numpy(float) if df["tdew_c"].notna().any() else None,
        rh_pct=df["rh_pct"].to_numpy(float) if df["rh_pct"].notna().any() else None,
        qc_flags=qc,
        precip_prov=precip_prov,
        met_prov=default_met_prov(),
        cell_id=cid,
    )
    info = CuratedInfo(
        cell_id=cid,
        n_days=len(df),
        fallback_share=fallback_share,
        column_mapping=mapping,
        missing_pct={
            c: round(100 * float(df[c].isna().mean()), 1)
            for c in ["precip_mm", "tmax_c", "tmin_c", "srad_mj_m2", "wind2m_ms"]
        },
        notes=notes,
        r1_et0_mm=df["et0_mm"].to_numpy(float) if "et0_mm" in df.columns else None,
    )
    return series, info
