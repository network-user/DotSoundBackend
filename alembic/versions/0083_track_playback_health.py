"""Track playback health: failures, events, auto-suppress window

Revision ID: 0083
Revises: 0082
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "playback_last_failure_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column("playback_last_http_status", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("playback_last_failure_source", sa.String(48), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "playback_recovery_failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "playback_suppressed_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_playback_suppressed_until",
        "tracks",
        ["playback_suppressed_until"],
        unique=False,
    )
    op.create_index(
        "ix_tracks_playback_last_failure_at",
        "tracks",
        ["playback_last_failure_at"],
        unique=False,
    )
    op.create_table(
        "track_playback_failure_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(48), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("detail_truncated", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_track_playback_failure_events_track_id_created",
        "track_playback_failure_events",
        ["track_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_track_playback_failure_events_source_created",
        "track_playback_failure_events",
        ["source", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_playback_failure_events_source_created",
        table_name="track_playback_failure_events",
    )
    op.drop_index(
        "ix_track_playback_failure_events_track_id_created",
        table_name="track_playback_failure_events",
    )
    op.drop_table("track_playback_failure_events")
    op.drop_index("ix_tracks_playback_last_failure_at", table_name="tracks")
    op.drop_index("ix_tracks_playback_suppressed_until", table_name="tracks")
    op.drop_column("tracks", "playback_suppressed_until")
    op.drop_column("tracks", "playback_recovery_failed_at")
    op.drop_column("tracks", "playback_last_failure_source")
    op.drop_column("tracks", "playback_last_http_status")
    op.drop_column("tracks", "playback_last_failure_at")
