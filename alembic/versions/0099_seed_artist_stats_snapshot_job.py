"""Seed monthly artist stats snapshot cron job.

Registers ``monthly-artist-stats-snapshot`` in ``scheduled_jobs``.
The same row is first inserted in revision 0069; this revision
upserts idempotently so upgrades do not fail on duplicate primary
key and align the display name with current copy.

Revision ID: 0099
Revises: 0098
Create Date: 2026-05-12
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None

_JOB_ID = "monthly-artist-stats-snapshot"
_TASK_NAME = (
    "app.services.artist_stats_worker:" "snapshot_monthly_artist_stats_task"
)
_CRON = "0 2 1 * *"
_QUEUE = "default"
_PAYLOAD = json.dumps({})
_NAME_UPGRADE = "Monthly artist stats snapshot"
_NAME_DOWNGRADE = "Snapshot artist monthly stats"


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
            name=_NAME_UPGRADE,
            task_name=_TASK_NAME,
            cron=_CRON,
            queue=_QUEUE,
            payload=_PAYLOAD,
            enabled=True,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE scheduled_jobs
            SET
                name = :name,
                task_name = :task_name,
                cron = :cron,
                queue = :queue,
                payload = CAST(:payload AS json),
                enabled = :enabled
            WHERE id = :id
            """
        ).bindparams(
            id=_JOB_ID,
            name=_NAME_DOWNGRADE,
            task_name=_TASK_NAME,
            cron=_CRON,
            queue=_QUEUE,
            payload=_PAYLOAD,
            enabled=True,
        )
    )
