"""add cover_blob_ref_freed and video_blob_ref_freed to tracks

Revision ID: 0053
Revises: 0052
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "cover_blob_ref_freed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "video_blob_ref_freed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "video_blob_ref_freed")
    op.drop_column("tracks", "cover_blob_ref_freed")
