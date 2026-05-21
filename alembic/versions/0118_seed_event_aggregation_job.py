"""Seed scheduled daily listen_events aggregation.

Revision ID: 0118
Revises: 0117
Create Date: 2026-05-21
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0118"
down_revision: str | None = "0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_ID = "listen-events-daily-aggregation"
_TASK_NAME = (
    "app.services.event_aggregation_worker" ":aggregate_listen_events_task"
)
_PAYLOAD = json.dumps({})


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO scheduled_jobs
                (id, name, task_name, cron, queue, payload, enabled)
            VALUES
                (
                    :id,
                    :name,
                    :task_name,
                    :cron,
                    :queue,
                    CAST(:payload AS json),
                    :enabled
                )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                task_name = EXCLUDED.task_name,
                cron = EXCLUDED.cron,
                queue = EXCLUDED.queue,
                payload = EXCLUDED.payload,
                enabled = EXCLUDED.enabled
            """
        ).bindparams(
            id=_JOB_ID,
            name="Aggregate raw listen_events into daily buckets",
            task_name=_TASK_NAME,
            cron="15 3 * * *",
            queue="default",
            payload=_PAYLOAD,
            enabled=True,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM scheduled_jobs WHERE id = :sid").bindparams(
            sid=_JOB_ID
        )
    )
