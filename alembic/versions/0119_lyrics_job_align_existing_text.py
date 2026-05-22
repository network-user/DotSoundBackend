"""Add lyrics_jobs.request_align_existing_text flag.

Revision ID: 0119
Revises: 0118
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "request_align_existing_text",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "lyrics_jobs",
        "request_align_existing_text",
    )
