"""add updated_at to lyrics_jobs

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-18
"""

from alembic import op


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE lyrics_jobs "
        "ADD COLUMN IF NOT EXISTS updated_at "
        "TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE lyrics_jobs DROP COLUMN IF EXISTS updated_at"
    )
