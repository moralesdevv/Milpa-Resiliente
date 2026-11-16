"""privilegios mínimos del rol de aplicación

Revision ID: 0013
Revises: 0012
"""

from api.db.migration_support import run_up

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0013_grants")


def downgrade() -> None:
    # Los privilegios se retiran al eliminar los objetos; no hay acción propia.
    pass
