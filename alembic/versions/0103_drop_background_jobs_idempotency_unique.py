"""drop background_jobs idempotency unique constraint

Revision ID: 0103
Revises: 0102
Create Date: 2026-05-16
"""

from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_background_jobs_idempotency_key",
        "background_jobs",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_background_jobs_idempotency_key",
        "background_jobs",
        ["idempotency_key"],
    )
