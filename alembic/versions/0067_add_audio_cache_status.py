"""add audio_cache_status to tracks

Revision ID: 0067
Revises: 0066
Create Date: 2026-04-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("audio_cache_status", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_tracks_audio_cache_status",
        "tracks",
        ["audio_cache_status"],
        postgresql_where=sa.text("audio_cache_status IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_audio_cache_status",
        table_name="tracks",
    )
    op.drop_column("tracks", "audio_cache_status")
