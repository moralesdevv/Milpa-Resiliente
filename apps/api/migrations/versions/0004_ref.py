"""ref (R1 provisional)

Revision ID: 0004
Revises: 0003
"""

from api.db.migration_support import run_statements, run_up

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0004_ref")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS ref.strategy_criteria, ref.strategy_cycle_component, ref.strategy_cycle, ref.strategy_version, ref.strategy, ref.food_composition, ref.reference_yield, ref.ph_tolerance, ref.risk_threshold, ref.crop_root_param, ref.phenology_stage, ref.crop_variety, ref.crop, ref.catalog_release, ref.soil_property CASCADE",
    )
