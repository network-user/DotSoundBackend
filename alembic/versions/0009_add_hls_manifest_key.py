"""Add hls_manifest_key to tracks

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("hls_manifest_key", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracks", "hls_manifest_key")
