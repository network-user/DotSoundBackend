"""add track catalog type

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "catalog_type",
            sa.String(length=32),
            server_default="ugc",
            nullable=False,
        ),
    )

    op.execute(
        "UPDATE tracks "
        "SET catalog_type = 'external_reference' "
        "WHERE source = 'soundcloud'"
    )
    op.execute(
        "UPDATE tracks "
        "SET catalog_type = 'ugc' "
        "WHERE source IN ('internal', 'telegram')"
    )


def downgrade() -> None:
    op.drop_column("tracks", "catalog_type")
