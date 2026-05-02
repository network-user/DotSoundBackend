"""extend artist_monthly_stats: add total_plays, total_likes, total_followers

Revision ID: 0070
Revises: 0069
Create Date: 2026-05-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artist_monthly_stats",
        sa.Column(
            "total_plays",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "artist_monthly_stats",
        sa.Column(
            "total_likes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "artist_monthly_stats",
        sa.Column(
            "total_followers",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("artist_monthly_stats", "total_followers")
    op.drop_column("artist_monthly_stats", "total_likes")
    op.drop_column("artist_monthly_stats", "total_plays")
