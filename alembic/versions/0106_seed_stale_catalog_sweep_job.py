"""Seed bi-weekly scheduled job: full catalog sync for stale artists.

Revision ID: 0106
Revises: 0105
Create Date: 2026-05-16
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: str | None = "0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_ID = "biweekly-stale-catalog-sweep"
_TASK_NAME = (
    "app.services.artist_catalog_sync_worker:sync_stale_catalogs_batch_task"
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
            name="Sweep stale full artist catalogs (bi-weekly)",
            task_name=_TASK_NAME,
            cron="0 4 1,15 * *",
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
