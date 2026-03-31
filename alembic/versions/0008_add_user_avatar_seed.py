"""Add avatar_seed to users

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "avatar_seed",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_users_avatar_seed",
        "users",
        ["avatar_seed"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_avatar_seed", "users", type_="unique")
    op.drop_column("users", "avatar_seed")
