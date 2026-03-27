"""Initial schema: users, tracks, playlists, playlist_tracks, likes

Revision ID: 0001
Revises:
Create Date: 2026-03-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "telegram_id", sa.BigInteger(), nullable=False
        ),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column(
            "first_name", sa.String(128), nullable=False
        ),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_users_telegram_id",
        "users",
        ["telegram_id"],
        unique=True,
    )

    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "title", sa.String(256), nullable=False
        ),
        sa.Column("artist", sa.String(256), nullable=True),
        sa.Column(
            "duration_seconds", sa.Integer(), nullable=True
        ),
        sa.Column("file_key", sa.Text(), nullable=False),
        sa.Column(
            "play_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tracks_title", "tracks", ["title"])
    op.create_index(
        "ix_tracks_artist", "tracks", ["artist"]
    )
    op.create_unique_constraint(
        "uq_tracks_file_key", "tracks", ["file_key"]
    )

    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "name", sa.String(256), nullable=False
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_playlists_owner_id", "playlists", ["owner_id"]
    )

    op.create_table(
        "playlist_tracks",
        sa.Column(
            "playlist_id",
            sa.Integer(),
            sa.ForeignKey(
                "playlists.id", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "likes",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("likes")
    op.drop_table("playlist_tracks")
    op.drop_index("ix_playlists_owner_id", "playlists")
    op.drop_table("playlists")
    op.drop_constraint(
        "uq_tracks_file_key", "tracks", type_="unique"
    )
    op.drop_index("ix_tracks_artist", "tracks")
    op.drop_index("ix_tracks_title", "tracks")
    op.drop_table("tracks")
    op.drop_index("ix_users_telegram_id", "users")
    op.drop_table("users")
