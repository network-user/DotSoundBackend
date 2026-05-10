"""Seed daily abuse_events retention pruner cron

Registers ``daily-abuse-events-pruner`` in ``scheduled_jobs``.
The task runs at ``15 4 * * *`` UTC (just after the daily
track hard-delete job at 04:00) and removes ``abuse_events``
rows older than the retention window from PrivateCore policy.

Revision ID: 0089
Revises: 0088
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None

_JOB_ID = "daily-abuse-events-pruner"


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
                    "Prune abuse_events past retention window"
                ),
                "task_name": (
                    "app.services."
                    "abuse_event_pruner_worker:"
                    "prune_abuse_events_task"
                ),
                "cron": "15 4 * * *",
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
