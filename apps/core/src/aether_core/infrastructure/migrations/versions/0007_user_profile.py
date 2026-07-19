"""Perfil do usuário: e-mail, nome de exibição e época do token.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(200), nullable=False, server_default=""))
    op.add_column(
        "users", sa.Column("display_name", sa.String(100), nullable=False, server_default="")
    )
    # Época do token: incrementada a cada troca de senha para invalidar as
    # sessões emitidas antes dela.
    op.add_column(
        "users", sa.Column("token_epoch", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    op.drop_column("users", "token_epoch")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
