"""Tarefas agendadas por instância: reinício, comando e backup.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("instance_id", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("schedule", sa.String(20), nullable=False),
        sa.Column("at_hour", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("at_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weekday", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("command", sa.Text(), nullable=False, server_default=""),
        sa.Column("warn_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run", sa.String(40), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_tasks_instance", "scheduled_tasks", ["instance_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_instance", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")
