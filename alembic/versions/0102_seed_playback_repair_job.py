"""Seed scheduled playback repair sweep.

Revision ID: 0102
Revises: 0101
Create Date: 2026-05-15
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: str | None = "0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_ID = "playback-repair-sweep"
_TASK_NAME = "app.services.playback_repair_worker:sweep_playback_repair_task"
_PAYLOAD = json.dumps({"limit": 30})


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
            name="Repair unavailable playback sources",
            task_name=_TASK_NAME,
            cron="*/20 * * * *",
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
