"""geo (R1 provisional)

Revision ID: 0005
Revises: 0004
"""

from api.db.migration_support import run_statements, run_up

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0005_geo")


def downgrade() -> None:
    run_statements(
        "ALTER TABLE ref.strategy DROP CONSTRAINT IF EXISTS strategy_region_fk",
        "DROP TABLE IF EXISTS geo.zone_cell, geo.climate_cell, geo.zone, geo.region CASCADE",
    )
