"""add avatar_blob_ref_freed to users

Revision ID: 0054
Revises: 0053
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "avatar_blob_ref_freed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_blob_ref_freed")
