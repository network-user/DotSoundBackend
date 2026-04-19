"""add artist source_profiles JSON column

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column("source_profiles", sa.JSON(), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column(
            "primary_source_id",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("artists", "primary_source_id")
    op.drop_column("artists", "source_profiles")
