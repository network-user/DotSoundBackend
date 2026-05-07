"""compute_workers: claims pause + worker package version

Revision ID: 0081
Revises: 0080
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compute_workers",
        sa.Column(
            "claims_paused_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "claims_pause_reason",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "worker_package_version",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "compute_workers",
        "worker_package_version",
    )
    op.drop_column(
        "compute_workers",
        "claims_pause_reason",
    )
    op.drop_column(
        "compute_workers",
        "claims_paused_until",
    )
