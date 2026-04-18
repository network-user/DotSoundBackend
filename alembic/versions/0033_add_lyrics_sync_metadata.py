"""add lyrics sync_quality and sync_profile metadata

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "track_lyrics",
        sa.Column(
            "sync_quality",
            sa.String(16),
            nullable=True,
        ),
    )
    op.add_column(
        "track_lyrics",
        sa.Column(
            "sync_profile",
            sa.String(16),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("track_lyrics", "sync_profile")
    op.drop_column("track_lyrics", "sync_quality")
