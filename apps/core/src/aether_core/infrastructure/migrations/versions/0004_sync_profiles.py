"""Sync profiles: signed manifests published per instance/channel.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("instance_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="stable"),
        sa.Column("rules", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("manifest", sa.Text(), nullable=True),
        sa.Column("signature", sa.String(200), nullable=True),
        sa.Column("published_at", sa.String(40), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_sync_instance", "sync_profiles", ["instance_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_instance", table_name="sync_profiles")
    op.drop_table("sync_profiles")
