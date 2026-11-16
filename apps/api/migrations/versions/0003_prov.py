"""prov (R1 provisional)

Revision ID: 0003
Revises: 0002
"""

from api.db.migration_support import run_statements, run_up

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0003_prov")


def downgrade() -> None:
    run_statements(
        "DROP TABLE IF EXISTS prov.indicator_provenance, prov.ingestion_run, prov.data_source, prov.citation CASCADE",
    )
