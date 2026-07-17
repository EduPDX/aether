"""Initial schema: instances and content cache.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instances",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("root_dir", sa.Text(), nullable=False),
        sa.Column("content_dirs", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "content_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("icon_file", sa.String(80), nullable=True),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("content_cache")
    op.drop_table("instances")
