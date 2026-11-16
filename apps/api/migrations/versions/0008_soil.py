"""soil (R1 provisional) + vista property_status

Revision ID: 0008
Revises: 0007
"""

from api.db.migration_support import run_statements, run_up

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0008_soil")


def downgrade() -> None:
    run_statements(
        "DROP VIEW IF EXISTS soil.property_status",
        "DROP TABLE IF EXISTS soil.estimate, soil.declaration, soil.measurement, soil.sample CASCADE",
    )
