"""Seed scheduled_jobs: deferred SC import verify sweep.

Runs every 5 minutes to verify playback for SoundCloud tracks that
were imported with skip_playback_verify=True (e.g. from recommendation
discovery imports).  Entries older than sc_import_verify_delay_minutes
and younger than sc_import_verify_ttl_minutes are processed in each run.

Revision ID: 0111
Revises: 0110
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0111"
down_revision: str | None = "0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "scheduled_jobs"

_JOBS = [
    {
        "id": "sc-deferred-import-verify",
        "name": "Verify SC tracks imported without playback check",
        "task_name": (
            "app.services.sc_import_verify_worker:"
            "verify_pending_sc_imports_task"
        ),
        "cron": "*/5 * * * *",
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
