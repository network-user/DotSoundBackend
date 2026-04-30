"""add artist_follows and artist_monthly_stats

Revision ID: 0068
Revises: 0067
Create Date: 2026-04-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artist_follows",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_artist_follows_artist_id",
        "artist_follows",
        ["artist_id"],
    )

    op.create_table(
        "artist_monthly_stats",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "year",
            sa.SmallInteger(),
            nullable=False,
        ),
        sa.Column(
            "month",
            sa.SmallInteger(),
            nullable=False,
        ),
        sa.Column(
            "unique_listeners",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "snapshotted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "artist_id",
            "year",
            "month",
            name="uq_artist_monthly_stats",
        ),
    )
    op.create_index(
        "ix_artist_monthly_stats_artist_id",
        "artist_monthly_stats",
        ["artist_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_artist_monthly_stats_artist_id",
        table_name="artist_monthly_stats",
    )
    op.drop_table("artist_monthly_stats")
    op.drop_index(
        "ix_artist_follows_artist_id",
        table_name="artist_follows",
    )
    op.drop_table("artist_follows")
