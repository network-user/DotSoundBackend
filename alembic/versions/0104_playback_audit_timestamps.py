"""add playback audit timestamps

Revision ID: 0104
Revises: 0103
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0104"
down_revision: str | None = "0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "playback_last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "playback_last_repair_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_playback_last_checked_at",
        "tracks",
        ["playback_last_checked_at"],
    )
    op.execute(
        sa.text(
            """
            UPDATE scheduled_jobs
            SET name = :name
            WHERE id = :sid
            """
        ).bindparams(
            sid="playback-repair-sweep",
            name="Audit and repair SoundCloud playback sources",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE scheduled_jobs
            SET name = :name
            WHERE id = :sid
            """
        ).bindparams(
            sid="playback-repair-sweep",
            name="Repair unavailable playback sources",
        )
    )
    op.drop_index(
        "ix_tracks_playback_last_checked_at",
        table_name="tracks",
    )
    op.drop_column("tracks", "playback_last_repair_attempt_at")
    op.drop_column("tracks", "playback_last_checked_at")
