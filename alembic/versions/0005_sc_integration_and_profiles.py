"""SoundCloud integration, public/private tracks, user profiles

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("tracks", "file_key", nullable=True)

    op.execute("ALTER TABLE tracks DROP CONSTRAINT IF EXISTS tracks_file_key_key")

    op.create_index(
        "ix_tracks_file_key_partial",
        "tracks",
        ["file_key"],
        unique=True,
        postgresql_where=text("file_key IS NOT NULL"),
    )

    op.add_column(
        "tracks",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="internal",
        ),
    )
    op.add_column(
        "tracks",
        sa.Column("sc_url", sa.Text, nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("sc_uri", sa.Text, nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "is_public",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
    )

    op.add_column(
        "users",
        sa.Column("avatar_key", sa.Text, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
    op.drop_column("users", "avatar_key")

    op.drop_column("tracks", "is_public")
    op.drop_column("tracks", "sc_uri")
    op.drop_column("tracks", "sc_url")
    op.drop_column("tracks", "source")

    op.drop_index("ix_tracks_file_key_partial", table_name="tracks")

    op.create_unique_constraint("tracks_file_key_key", "tracks", ["file_key"])

    op.alter_column("tracks", "file_key", nullable=False)
