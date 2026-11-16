"""engine: corridas, resultados, job

Revision ID: 0010
Revises: 0009
"""

from api.db.migration_support import run_statements, run_up

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0010_engine")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS engine.job, engine.soil_voi_result, engine.ranking_stability, engine.ranking_result, engine.planting_summary, engine.risk_summary, engine.scenario_run, engine.scenario_def CASCADE",
        "ALTER TABLE prov.indicator_provenance DROP CONSTRAINT IF EXISTS indicator_provenance_run_id_fkey",
        "DROP TABLE IF EXISTS engine.analysis_run CASCADE",
    )
