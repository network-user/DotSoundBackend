"""co listen rooms, playlist collab, track snippets

Revision ID: 0056
Revises: 0055
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "co_listen_rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "host_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dj_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_playing",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_co_listen_rooms_host", "co_listen_rooms", ["host_id"]
    )
    op.create_index(
        "ix_co_listen_rooms_expires", "co_listen_rooms", ["expires_at"]
    )

    op.create_table(
        "playlist_collaborators",
        sa.Column(
            "playlist_id",
            sa.Integer(),
            sa.ForeignKey("playlists.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="editor"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_playlist_collab_user", "playlist_collaborators", ["user_id"]
    )

    op.create_table(
        "playlist_invite_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "playlist_id",
            sa.Integer(),
            sa.ForeignKey("playlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inviter_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_role", sa.String(20), nullable=False, server_default="editor"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_playlist_invite_playlist", "playlist_invite_tokens", ["playlist_id"]
    )

    op.create_table(
        "track_snippets",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_key", sa.Text(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_track_snippets_track", "track_snippets", ["track_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_track_snippets_track", "track_snippets")
    op.drop_table("track_snippets")
    op.drop_index("ix_playlist_invite_playlist", "playlist_invite_tokens")
    op.drop_table("playlist_invite_tokens")
    op.drop_index("ix_playlist_collab_user", "playlist_collaborators")
    op.drop_table("playlist_collaborators")
    op.drop_index("ix_co_listen_rooms_expires", "co_listen_rooms")
    op.drop_index("ix_co_listen_rooms_host", "co_listen_rooms")
    op.drop_table("co_listen_rooms")
