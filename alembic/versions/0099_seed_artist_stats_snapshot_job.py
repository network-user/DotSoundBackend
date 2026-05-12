"""Seed monthly artist stats snapshot cron job.

Registers ``monthly-artist-stats-snapshot`` in ``scheduled_jobs``.
The task runs at ``0 2 1 * *`` UTC (02:00 on the 1st of each month)
and snapshots the previous month's unique listeners, plays, likes,
and follower counts for all artists into ``artist_monthly_stats``.

Revision ID: 0099
Revises: 0098
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None

_JOB_ID = "monthly-artist-stats-snapshot"


def upgrade() -> None:
    jobs_table = sa.table(
        "scheduled_jobs",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("task_name", sa.String),
        sa.column("cron", sa.String),
        sa.column("queue", sa.String),
        sa.column("payload", sa.JSON),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        jobs_table,
        [
            {
                "id": _JOB_ID,
                "name": (
                    "Monthly artist stats snapshot"
                ),
                "task_name": (
                    "app.services."
                    "artist_stats_worker:"
                    "snapshot_monthly_artist_stats_task"
                ),
                "cron": "0 2 1 * *",
                "queue": "default",
                "payload": {},
                "enabled": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM scheduled_jobs WHERE id = :sid"
        ).bindparams(sid=_JOB_ID)
    )
