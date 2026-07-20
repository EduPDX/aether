"""Cache das versões de servidor que cada provider oferece.

Listar versões custa um container efêmero falando com a Steam — segundos de
espera toda vez que alguém abre a tela de criar servidor, e uma requisição a
mais para um serviço de terceiro que não nos deve nada. O resultado muda poucas
vezes por semana; guardá-lo no banco tira a espera do caminho do usuário e a
lista continua existindo quando a origem está fora do ar.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_versions",
        sa.Column("provider_id", sa.String(64), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.String(40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_versions")
