"""Add catalog_sync_enabled flag to artists table.

Artists discovered via SoundCloud station resolution are marked
catalog_sync_enabled=False so their catalog is not auto-synced
on every enrichment cycle. Admin and follow actions can flip the
flag to True to opt an artist back into the sync pipeline.

Revision ID: 0107
Revises: 0106
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0107"
down_revision: str | None = "0106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column(
            "catalog_sync_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_artists_catalog_sync_enabled",
        "artists",
        ["catalog_sync_enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_artists_catalog_sync_enabled",
        table_name="artists",
    )
    op.drop_column("artists", "catalog_sync_enabled")
