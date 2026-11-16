"""farm: farmer, parcel, history, profile, assignment

Revision ID: 0006
Revises: 0005
"""

from api.db.migration_support import run_statements, run_up

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0006_farm")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS farm.technician_assignment, farm.priority_profile, farm.parcel_history, farm.parcel, farm.farmer CASCADE",
    )
