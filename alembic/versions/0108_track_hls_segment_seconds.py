"""Track HLS bundle version + segment duration.

Adds two nullable columns so the playback pipeline can tell which
HLS layout each track uses and the migration worker can find old
bundles transcoded with 10-second segments.

Revision ID: 0108
Revises: 0107
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0108"
down_revision: str | None = "0107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "hls_segment_seconds",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "hls_bundle_version",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_hls_bundle_version",
        "tracks",
        ["hls_bundle_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_hls_bundle_version",
        table_name="tracks",
    )
    op.drop_column("tracks", "hls_bundle_version")
    op.drop_column("tracks", "hls_segment_seconds")
