"""Seed scheduled_jobs: daily recommendation-cache pre-warmer.

Runs once a day at 00:05 UTC — five minutes after midnight, when the
per-user ``rec:daily_mix:*`` and ``rec:genre_mixes:*`` TTLs have just
expired — to rebuild the caches for recently active users.

Revision ID: 0110
Revises: 0109
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0110"
down_revision: str | None = "0109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "scheduled_jobs"

_JOBS = [
    {
        "id": "daily-rec-cache-warmup",
        "name": "Pre-warm daily-mix + genre-mixes caches",
        "task_name": (
            "app.tasks.rec_cache_warmer:"
            "dispatch_rec_cache_warmup_task"
        ),
        "cron": "5 0 * * *",
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
        ).bindparams(ids=tuple(j["id"] for j in _JOBS))
    )
