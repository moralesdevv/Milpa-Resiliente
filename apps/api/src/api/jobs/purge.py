"""Operaciones de borrado definitivo (spec R3 §9.7). Parcela + datos dependientes + archivos.

Orden: (1) se listan los archivos y se guarda un checkpoint, (2) se borran las filas en una sola
transacción, (3) se borran los archivos. Si el proceso muere entre (2) y (3), la re-ejecución del
trabajo (idempotente) completa el borrado de archivos desde el checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.storage.object_store import ObjectStore, StoragePathError


@dataclass
class Artifacts:
    result_dirs: list[str] = field(default_factory=list)
    pdfs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"result_dirs": self.result_dirs, "pdfs": self.pdfs}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Artifacts:
        return cls(list(d.get("result_dirs", [])), list(d.get("pdfs", [])))


def run_ids_for_parcel(s: Session, parcel_id: UUID) -> list[UUID]:
    rows = s.execute(
        text("SELECT run_id FROM engine.analysis_run WHERE parcel_id = :p"), {"p": parcel_id}
    )
    return [r[0] for r in rows]


def collect_artifacts(s: Session, run_ids: list[UUID]) -> Artifacts:
    pdfs = [
        r[0]
        for r in s.execute(
            text(
                "SELECT pdf_uri FROM report.report WHERE run_id = ANY(:r) AND pdf_uri IS NOT NULL"
            ),
            {"r": run_ids},
        )
    ]
    return Artifacts(result_dirs=[f"results/{r}" for r in run_ids], pdfs=pdfs)


def purge_run_data(s: Session, run_ids: list[UUID], parcel_id: UUID | None = None) -> None:
    """Borra informes, rankings, resúmenes, escenarios, procedencia y corridas de las corridas dadas."""
    p = {"r": run_ids, "p": parcel_id}
    stmts = [
        "DELETE FROM report.report WHERE run_id = ANY(:r)",
        "DELETE FROM engine.soil_voi_result WHERE run_id = ANY(:r) OR (:p IS NOT NULL AND parcel_id = :p)",
        "DELETE FROM engine.ranking_stability WHERE ranking_id IN "
        "(SELECT ranking_id FROM engine.ranking_result WHERE run_id = ANY(:r))",
        "DELETE FROM engine.ranking_result WHERE run_id = ANY(:r)",
        "DELETE FROM engine.risk_summary WHERE run_id = ANY(:r)",
        "DELETE FROM engine.planting_summary WHERE run_id = ANY(:r)",
        "DELETE FROM engine.scenario_run WHERE run_id = ANY(:r)",
        "DELETE FROM prov.indicator_provenance WHERE run_id = ANY(:r)",
        "DELETE FROM engine.analysis_run WHERE run_id = ANY(:r)",
    ]
    for stmt in stmts:
        s.execute(text(stmt), p)


def purge_parcel_rows(s: Session, parcel_id: UUID) -> None:
    ips = [
        r[0]
        for r in s.execute(
            text(
                """
                SELECT m.ip_id FROM soil.measurement m JOIN soil.sample sa USING (sample_id)
                  WHERE sa.parcel_id = :p
                UNION SELECT ip_id FROM soil.declaration WHERE parcel_id = :p
                UNION SELECT ip_id FROM farm.parcel_history WHERE parcel_id = :p AND ip_id IS NOT NULL
                """
            ),
            {"p": parcel_id},
        )
    ]
    p = {"p": parcel_id}
    for stmt in [
        "DELETE FROM soil.measurement WHERE sample_id IN (SELECT sample_id FROM soil.sample WHERE parcel_id = :p)",
        "DELETE FROM soil.sample WHERE parcel_id = :p",
        "DELETE FROM soil.declaration WHERE parcel_id = :p",
        "DELETE FROM farm.parcel_history WHERE parcel_id = :p",
        "DELETE FROM farm.priority_profile WHERE parcel_id = :p",
        "DELETE FROM private.parcel_geometry WHERE parcel_id = :p",
    ]:
        s.execute(text(stmt), p)
    if ips:
        s.execute(text("DELETE FROM prov.indicator_provenance WHERE ip_id = ANY(:i)"), {"i": ips})
    s.execute(text("DELETE FROM farm.parcel WHERE parcel_id = :p"), p)


def delete_artifacts(store: ObjectStore, art: Artifacts) -> int:
    removed = 0
    for d in art.result_dirs:
        try:
            removed += int(store.delete_tree(d))
        except StoragePathError:
            continue
    for f in art.pdfs:
        try:
            removed += int(store.delete(f))
        except StoragePathError:
            continue
    return removed
