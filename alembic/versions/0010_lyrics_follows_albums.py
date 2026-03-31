"""Add track_lyrics, user_follows, albums tables and tracks.album_id

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- albums ---
    op.create_table(
        "albums",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cover_key", sa.Text, nullable=True),
        sa.Column(
            "owner_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_public",
            sa.Boolean,
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- track_lyrics ---
    op.create_table(
        "track_lyrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "track_id",
            sa.Integer,
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("plain_text", sa.Text, nullable=False),
        sa.Column("synced_lines", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- user_follows ---
    op.create_table(
        "user_follows",
        sa.Column(
            "follower_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "following_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "follower_id != following_id", name="ck_no_self_follow"
        ),
    )
    op.create_index(
        "ix_user_follows_following_id",
        "user_follows",
        ["following_id"],
    )

    # --- tracks.album_id ---
    op.add_column(
        "tracks",
        sa.Column(
            "album_id",
            sa.Integer,
            sa.ForeignKey("albums.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "album_id")
    op.drop_index("ix_user_follows_following_id", table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_table("track_lyrics")
    op.drop_table("albums")
