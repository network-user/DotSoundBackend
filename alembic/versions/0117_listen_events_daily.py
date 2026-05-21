"""Daily aggregate table for listen_events.

Long-tail raw rows are folded into per-(day, user, track) buckets so
the raw table can be trimmed. Stats consumers read the union of
recent raw rows + older daily aggregates.

Revision ID: 0117
Revises: 0116
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0117"
down_revision: str | None = "0116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listen_events_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("track_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "plays",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "listen_seconds",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "completes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "skips",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "day",
            "user_id",
            "track_id",
            name="pk_listen_events_daily",
        ),
    )
    op.create_index(
        "ix_listen_events_daily_track_day",
        "listen_events_daily",
        ["track_id", "day"],
    )
    op.create_index(
        "ix_listen_events_daily_user_day",
        "listen_events_daily",
        ["user_id", "day"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_listen_events_daily_user_day",
        table_name="listen_events_daily",
    )
    op.drop_index(
        "ix_listen_events_daily_track_day",
        table_name="listen_events_daily",
    )
    op.drop_table("listen_events_daily")
