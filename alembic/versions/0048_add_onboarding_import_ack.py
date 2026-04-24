"""add onboarding_import_acknowledged to user_preferences

Tracks whether the user has passed (or skipped) the dedicated import
onboarding step. Backfill true for users who already finished main
onboarding so they are not shown the new step on upgrade.

Revision ID: 0048
Revises: 0047
Create Date: 2026-04-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "onboarding_import_acknowledged",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE user_preferences "
            "SET onboarding_import_acknowledged = true "
            "WHERE onboarding_completed = true"
        )
    )


def downgrade() -> None:
    op.drop_column(
        "user_preferences", "onboarding_import_acknowledged"
    )
