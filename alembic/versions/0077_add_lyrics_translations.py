"""add per-track lyrics translations

Revision ID: 0077
Revises: 0076
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_lyrics_translations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("track_lyrics_id", sa.Integer(), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["track_lyrics_id"],
            ["track_lyrics.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "track_lyrics_id",
            "language_code",
            name="uq_track_lyrics_translations_language",
        ),
    )
    op.create_index(
        op.f("ix_track_lyrics_translations_track_lyrics_id"),
        "track_lyrics_translations",
        ["track_lyrics_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_track_lyrics_translations_track_lyrics_id"),
        table_name="track_lyrics_translations",
    )
    op.drop_table("track_lyrics_translations")
