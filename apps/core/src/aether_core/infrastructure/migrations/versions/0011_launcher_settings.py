"""Configurações públicas de apresentação e conexão do launcher."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "launcher_settings",
        sa.Column("instance_id", sa.String(32), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("launcher_settings")
