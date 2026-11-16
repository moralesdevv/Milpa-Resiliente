"""private.parcel_geometry

Revision ID: 0007
Revises: 0006
"""

from api.db.migration_support import run_statements, run_up

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0007_private")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS private.parcel_geometry CASCADE",
    )
