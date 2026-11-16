"""Lectura de corridas/escenarios persistidos, procedencia, catálogos (R1) e informes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from api.contracts.provisional_enums import AdaptationMode
from api.models.engine import AnalysisRun, ScenarioRun
from api.models.ref import Citation, Crop, Strategy, StrategyVersion
from api.models.report import Report


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, run_id: UUID) -> AnalysisRun | None:
        return self.s.get(AnalysisRun, run_id)

    def scenarios(self, run_id: UUID) -> list[ScenarioRun]:
        return list(
            self.s.scalars(
                select(ScenarioRun)
                .where(ScenarioRun.run_id == run_id)
                .order_by(ScenarioRun.scenario_id, ScenarioRun.adaptation_mode)
            )
        )

    def catalog_hash(self, release_id: UUID) -> str | None:
        value = self.s.execute(
            text("SELECT catalog_hash FROM ref.catalog_release WHERE catalog_release_id = :i"),
            {"i": release_id},
        ).scalar_one_or_none()
        return None if value is None else str(value).strip()

    def scenario_tags(self, run_id: UUID) -> list[dict[str, Any]]:
        """Escenarios ya calculados de una corrida, con los parámetros de ``scenario_def``."""
        rows = self.s.execute(
            text(
                """
                SELECT sr.scenario_id, d.label, d.delta_t_c, d.precip_factor, d.onset_delay_days,
                       d.humidity_assumption::text AS humidity_assumption,
                       sr.adaptation_mode::text AS adaptation_mode, d.method_doc,
                       sr.engine_version, sr.executed_at
                FROM engine.scenario_run sr JOIN engine.scenario_def d USING (scenario_id)
                WHERE sr.run_id = :r AND sr.status = 'ok'
                ORDER BY sr.scenario_id, sr.adaptation_mode
                """
            ),
            {"r": run_id},
        ).mappings()
        return [dict(r) for r in rows]

    def scenario(self, run_id: UUID, scenario_id: str, adaptation: str) -> ScenarioRun | None:
        return self.s.get(ScenarioRun, (run_id, scenario_id, AdaptationMode(adaptation)))


class ProvenanceRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_detail(self, ip_id: UUID) -> dict[str, Any] | None:
        """None si no existe O si el usuario no puede acceder (anti-enumeración)."""
        row = (
            self.s.execute(
                text(
                    """
                    SELECT ip_id, run_id, indicator_code, unit, provenance::text AS provenance,
                           evidence_level::text AS evidence_level, evidence_rule_id, source_ids,
                           dataset_version, period_start, period_end, spatial_res_m, temporal_res,
                           processing_method, retrieved_at, missing_pct, assumptions, limitations
                    FROM prov.indicator_provenance
                    WHERE ip_id = :ip AND prov.can_access_ip(ip_id)
                    """
                ),
                {"ip": ip_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        detail = dict(row)
        sources = self.s.execute(
            text(
                """
                SELECT s.source_id, s.code, s.product_name, s.institution, s.is_nasa, s.version,
                       s.access_url AS url, c.full_text AS citation
                FROM prov.data_source s LEFT JOIN prov.citation c USING (citation_id)
                WHERE s.source_id = ANY(:ids) ORDER BY s.source_id
                """
            ),
            {"ids": list(detail["source_ids"] or [])},
        ).mappings()
        detail["sources"] = [dict(s) for s in sources]
        return detail


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def crops(self) -> list[Crop]:
        return list(self.s.scalars(select(Crop).order_by(Crop.code)))

    def strategies(self) -> list[Strategy]:
        return list(self.s.scalars(select(Strategy).order_by(Strategy.code)))

    def latest_versions(self) -> dict[UUID, int]:
        rows = self.s.execute(
            text(
                "SELECT strategy_id, max(version) AS v FROM ref.strategy_version GROUP BY strategy_id"
            )
        ).all()
        return {r[0]: int(r[1]) for r in rows}

    def strategy_version(self, strategy_id: UUID, version: int) -> StrategyVersion | None:
        return self.s.scalar(
            select(StrategyVersion).where(
                StrategyVersion.strategy_id == strategy_id, StrategyVersion.version == version
            )
        )

    def cycles(self, strategy_version_id: UUID) -> list[dict[str, Any]]:
        cycles = (
            self.s.execute(
                text(
                    """
                    SELECT cycle_idx, agri_year_offset, season, window_mode::text AS window_mode,
                           plant_window_start, plant_window_end, rel_lag_days, fallow_after_days,
                           soil_carryover
                    FROM ref.strategy_cycle WHERE strategy_version_id = :v ORDER BY cycle_idx
                    """
                ),
                {"v": strategy_version_id},
            )
            .mappings()
            .all()
        )
        comps = (
            self.s.execute(
                text(
                    """
                    SELECT k.cycle_idx, k.variety_id, k.role, k.area_fraction, k.plant_offset_days,
                           c.code AS crop_code, c.name_es AS crop_name_es, c.name_en AS crop_name_en
                    FROM ref.strategy_cycle_component k
                    LEFT JOIN ref.crop_variety v ON v.variety_id = k.variety_id
                    LEFT JOIN ref.crop c ON c.crop_id = v.crop_id
                    WHERE k.strategy_version_id = :v
                    ORDER BY k.cycle_idx, k.variety_id
                    """
                ),
                {"v": strategy_version_id},
            )
            .mappings()
            .all()
        )
        out = []
        for c in cycles:
            d = dict(c)
            d["components"] = [dict(k) for k in comps if k["cycle_idx"] == c["cycle_idx"]]
            out.append(d)
        return out

    def references(self) -> list[Citation]:
        return list(self.s.scalars(select(Citation).order_by(Citation.bibkey)))


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, report_id: UUID) -> Report | None:
        return self.s.get(Report, report_id)  # RLS

    def add(self, report: Report) -> Report:
        self.s.add(report)
        self.s.flush()
        return report
