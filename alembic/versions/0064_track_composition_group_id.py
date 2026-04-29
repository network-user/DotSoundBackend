"""tracks.composition_group_id for explicit playback variant groups

Revision ID: 0064
Revises: 0063
Create Date: 2026-04-29
"""

import sqlalchemy as sa

from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "composition_group_id",
            sa.String(length=36),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_composition_group_id",
        "tracks",
        ["composition_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tracks_composition_group_id", table_name="tracks")
    op.drop_column("tracks", "composition_group_id")
