"""extensiones, esquemas y tipos

Revision ID: 0001
Revises:
"""

from api.db.migration_support import run_statements, run_up

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0001_base")


def downgrade() -> None:
    run_statements(
        "DROP TYPE IF EXISTS job_status_t, user_role_t, window_mode_t, strategy_axis_t, humidity_t, adaptation_t, voi_outcome_t, voi_applicability_t, stability_flag_t, ranking_status_t, criterion_status_t, cell_state_t, label_t, mode_t, property_status_t, evidence_t, provenance_t CASCADE",
        "DROP SCHEMA IF EXISTS report, engine, econ, soil, private, farm, geo, ref, prov, auth CASCADE",
    )
