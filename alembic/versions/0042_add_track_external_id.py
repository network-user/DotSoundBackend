"""add tracks.external_id

Revision ID: 0042
Revises: 0041
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "external_id",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tracks_imported_from_external_id",
        "tracks",
        ["imported_from", "external_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_imported_from_external_id",
        table_name="tracks",
    )
    op.drop_column("tracks", "external_id")
