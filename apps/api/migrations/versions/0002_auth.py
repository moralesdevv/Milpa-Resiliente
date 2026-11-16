"""auth: app_user, consent, audit_log

Revision ID: 0002
Revises: 0001
"""

from api.db.migration_support import run_statements, run_up

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0002_auth")


def downgrade() -> None:
    run_statements(
        "DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth",
    )
