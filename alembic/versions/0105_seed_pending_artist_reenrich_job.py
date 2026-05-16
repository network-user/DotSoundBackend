"""Seed daily scheduled job: re-enrich stuck pending/in_progress artists.

Revision ID: 0105
Revises: 0104
Create Date: 2026-05-16
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0105"
down_revision: str | None = "0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_ID = "daily-pending-artist-reenrich"
_TASK_NAME = (
    "app.services.artist_enrichment_worker:re_enrich_pending_artists_task"
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
            name="Re-enrich stuck pending/in-progress artists",
            task_name=_TASK_NAME,
            cron="0 5 * * *",
            queue="default",
            payload=_PAYLOAD,
            enabled=True,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM scheduled_jobs WHERE id = :sid"
        ).bindparams(sid=_JOB_ID)
    )
