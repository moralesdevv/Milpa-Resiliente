"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
