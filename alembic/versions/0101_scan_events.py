"""Add scan_events table for antivirus audit log.

Revision ID: 0101
Revises: 0100
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0101"
down_revision: str | None = "0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scan_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "filename", sa.String(length=512), nullable=False
        ),
        sa.Column(
            "file_size", sa.BigInteger(), nullable=True
        ),
        sa.Column(
            "verdict", sa.String(length=16), nullable=False
        ),
        sa.Column("threat_name", sa.Text(), nullable=True),
        sa.Column(
            "scan_mode", sa.String(length=16), nullable=False
        ),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scan_events_verdict",
        "scan_events",
        ["verdict"],
    )
    op.create_index(
        "ix_scan_events_scanned_at",
        "scan_events",
        ["scanned_at"],
    )
    op.create_index(
        "ix_scan_events_verdict_scanned_at",
        "scan_events",
        ["verdict", "scanned_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scan_events_verdict_scanned_at",
        table_name="scan_events",
    )
    op.drop_index(
        "ix_scan_events_scanned_at",
        table_name="scan_events",
    )
    op.drop_index(
        "ix_scan_events_verdict",
        table_name="scan_events",
    )
    op.drop_table("scan_events")
