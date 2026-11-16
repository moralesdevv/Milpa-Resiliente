"""econ (R1 provisional)

Revision ID: 0009
Revises: 0008
"""

from api.db.migration_support import run_statements, run_up

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0009_econ")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS econ.cost_record, econ.price_record CASCADE",
    )
