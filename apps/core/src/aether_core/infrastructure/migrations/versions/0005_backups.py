"""Backups: arquivos gerados por instância e política de retenção.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("instance_id", sa.String(32), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_backups_instance", "backups", ["instance_id"])

    # Uma linha por instância: agendamento, retenção e quando rodou por último.
    op.create_table(
        "backup_policies",
        sa.Column("instance_id", sa.String(32), primary_key=True),
        sa.Column("schedule", sa.String(20), nullable=False, server_default="off"),
        sa.Column("keep", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("last_run", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("backup_policies")
    op.drop_index("ix_backups_instance", table_name="backups")
    op.drop_table("backups")
