"""add tracks.imported_from

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "imported_from",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE tracks "
        "SET imported_from = 'telegram' "
        "WHERE source_platform = 'telegram'"
    )


def downgrade() -> None:
    op.drop_column("tracks", "imported_from")
