"""Add editorial playlist fields (type, featured, source_url, cover_key, description)

Revision ID: 0081
Revises: 0080
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column(
            "playlist_type",
            sa.String(50),
            nullable=False,
            server_default="user",
        ),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "source_url",
            sa.String(1024),
            nullable=True,
        ),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "cover_key",
            sa.String(512),
            nullable=True,
        ),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "description",
            sa.String(512),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_playlists_is_featured",
        "playlists",
        ["is_featured"],
    )


def downgrade() -> None:
    op.drop_index("ix_playlists_is_featured", table_name="playlists")
    op.drop_column("playlists", "description")
    op.drop_column("playlists", "cover_key")
    op.drop_column("playlists", "source_url")
    op.drop_column("playlists", "is_featured")
    op.drop_column("playlists", "playlist_type")
