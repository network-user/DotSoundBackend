"""lyrics_jobs queue pin/priority; compute_jobs worker pin

Revision ID: 0076
Revises: 0075
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "pinned_worker_id",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "queue_priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "compute_jobs",
        sa.Column(
            "pinned_worker_id",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("compute_jobs", "pinned_worker_id")
    op.drop_column("lyrics_jobs", "queue_priority")
    op.drop_column("lyrics_jobs", "pinned_worker_id")
