"""report.report

Revision ID: 0011
Revises: 0010
"""

from api.db.migration_support import run_statements, run_up

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0011_report")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS report.report CASCADE",
    )
