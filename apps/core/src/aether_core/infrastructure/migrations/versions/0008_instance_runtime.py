"""Add instances.runtime (process | docker).

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default 'process': toda instância pré-existente rodava como processo
    # local, então a migração não muda comportamento de ninguém.
    op.add_column(
        "instances",
        sa.Column("runtime", sa.String(length=20), nullable=False, server_default="process"),
    )


def downgrade() -> None:
    op.drop_column("instances", "runtime")
