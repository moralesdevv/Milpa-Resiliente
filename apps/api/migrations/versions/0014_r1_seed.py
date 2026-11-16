"""datos de referencia de R1: fuentes de datos y catálogo de propiedades de suelo

Revision ID: 0014
Revises: 0013
"""

from alembic import op

from api.db.migration_support import run_up

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0014_r1_seed")


def downgrade() -> None:
    op.execute(
        "DELETE FROM ref.soil_property WHERE code IN "
        "('ph','organic_matter','sand','silt','clay','cec','effective_depth','awc')"
    )
    op.execute(
        "DELETE FROM prov.data_source WHERE code IN ('POWER_DAILY','IMERG_FINAL_V07','SOIL_CSV_FIXTURE') "
        "AND NOT EXISTS (SELECT 1 FROM prov.indicator_provenance p WHERE data_source.source_id = ANY(p.source_ids))"
    )
