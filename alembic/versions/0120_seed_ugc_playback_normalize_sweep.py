"""Seed scheduled internal UGC playback normalize sweep.

Revision ID: 0120
Revises: 0119
Create Date: 2026-05-27
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0120"
down_revision: str | None = "0119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_ID = "ugc-playback-normalize-sweep"
_TASK_NAME = (
    "app.services.ugc_playback_normalize_service:"
    "sweep_ugc_playback_normalize_task"
)
_PAYLOAD = json.dumps({"limit": 40})


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
            name="Normalize internal UGC playback (MP3 + HLS)",
            task_name=_TASK_NAME,
            cron="15 */6 * * *",
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
