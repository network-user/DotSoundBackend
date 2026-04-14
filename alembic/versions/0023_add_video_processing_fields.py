"""add video processing status and thumbnail

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "video_processing_status",
            sa.String(20),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "video_thumbnail_key",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "video_thumbnail_key")
    op.drop_column("tracks", "video_processing_status")
