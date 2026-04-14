"""add user locale

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(10),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "locale")
