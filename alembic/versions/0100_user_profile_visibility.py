"""Add user.profile_visibility for public profile access control.

Revision ID: 0100
Revises: 0099
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0100"
down_revision: str | None = "0099"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "profile_visibility",
            sa.String(20),
            nullable=False,
            server_default="public",
        ),
    )
    op.create_check_constraint(
        "ck_users_profile_visibility",
        "users",
        "profile_visibility IN ('public', 'followers_only', 'hidden')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_profile_visibility",
        "users",
        type_="check",
    )
    op.drop_column("users", "profile_visibility")
