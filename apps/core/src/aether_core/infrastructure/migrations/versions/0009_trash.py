"""Lixeira: guarda a origem de cada item para permitir restaurar.

Antes disto o Core movia o arquivo para uma pasta e esquecia de onde ele tinha
saído, então a lixeira era um caminho de mão única: a interface prometia
"mover para a lixeira" e não havia como voltar.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trash_items",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("instance_id", sa.String(32), nullable=False),
        # Relativo à raiz da instância — é o que permite devolver ao lugar.
        sa.Column("original_path", sa.Text(), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False),
        sa.Column("is_dir", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="files"),
        sa.Column("content_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("trashed_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_trash_instance", "trash_items", ["instance_id"])


def downgrade() -> None:
    op.drop_index("ix_trash_instance", table_name="trash_items")
    op.drop_table("trash_items")
