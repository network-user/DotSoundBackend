"""Add metadata to tracks

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "file_size_bytes",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "genre",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_tracks_genre"), "tracks", ["genre"], unique=False
    )
    op.add_column(
        "tracks",
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "processing_status")
    op.drop_index(op.f("ix_tracks_genre"), table_name="tracks")
    op.drop_column("tracks", "genre")
    op.drop_column("tracks", "file_size_bytes")
