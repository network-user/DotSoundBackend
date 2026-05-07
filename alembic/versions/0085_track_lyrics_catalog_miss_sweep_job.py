"""track lyrics_catalog_miss marker + hourly lyrics sweep scheduled job

Revision ID: 0085
Revises: 0084
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None

_TABLE = "scheduled_jobs"

_JOB = {
    "id": "lyrics-discovery-sweep-hourly",
    "name": "Enqueue catalog lyrics sweep for tracks without lyrics",
    "task_name": (
        "app.services.lyrics_discovery_sweep:" "lyrics_discovery_sweep_task"
    ),
    "cron": "20 * * * *",
    "queue": "default",
    "payload": {},
    "enabled": True,
}


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "lyrics_catalog_miss_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_lyrics_catalog_miss_at",
        "tracks",
        ["lyrics_catalog_miss_at"],
    )
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
    op.bulk_insert(jobs_table, [_JOB])


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM scheduled_jobs WHERE id = :sid").bindparams(
            sid=_JOB["id"],
        ),
    )
    op.drop_index(
        "ix_tracks_lyrics_catalog_miss_at",
        table_name="tracks",
    )
    op.drop_column("tracks", "lyrics_catalog_miss_at")
