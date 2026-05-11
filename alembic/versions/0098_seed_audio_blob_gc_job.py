"""Seed the daily audio-blob GC scheduled job.

Runs once a day at 04:00 UTC, reconciles ``audio_blobs`` rows against
S3 objects under ``blobs/`` and ``hls-blobs/``, and drops orphans older
than a safety window.

Revision ID: 0098
Revises: 0097
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None

_JOB_ID = "audio-blob-orphan-gc"


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
                    "Reconcile audio_blobs/HLS bundles and drop orphans"
                ),
                "task_name": (
                    "app.services.audio_blob_gc_worker:gc_audio_blobs_task"
                ),
                "cron": "0 4 * * *",
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
