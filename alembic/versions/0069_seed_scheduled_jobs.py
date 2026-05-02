"""seed scheduled_jobs: monthly stats snapshot + weekly station sweep

Revision ID: 0069
Revises: 0068
Create Date: 2026-05-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

_TABLE = "scheduled_jobs"

_JOBS = [
    {
        "id": "monthly-artist-stats-snapshot",
        "name": "Snapshot artist monthly stats",
        "task_name": "app.services.artist_stats_worker:snapshot_monthly_artist_stats_task",
        "cron": "0 2 1 * *",
        "queue": "default",
        "payload": {},
        "enabled": True,
    },
    {
        "id": "weekly-station-stale-sweep",
        "name": "Sweep stale SC artist stations",
        "task_name": "app.services.artist_catalog_sync_worker:sync_stale_stations_batch_task",
        "cron": "0 3 * * 1",
        "queue": "default",
        "payload": {},
        "enabled": True,
    },
]


def upgrade() -> None:
    jobs_table = sa.table(
        _TABLE,
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("task_name", sa.String),
        sa.column("cron", sa.String),
        sa.column("queue", sa.String),
        sa.column("payload", sa.JSON),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(jobs_table, _JOBS)


def downgrade() -> None:
    op.execute(
        sa.text(
            f"DELETE FROM {_TABLE} WHERE id IN :ids"
        ).bindparams(
            ids=tuple(j["id"] for j in _JOBS)
        )
    )
