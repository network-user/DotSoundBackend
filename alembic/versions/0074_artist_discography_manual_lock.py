"""artist discography manual lock

Revision ID: 0074
Revises: 0073
Create Date: 2026-05-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column(
            "discography_manual_lock",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("artists", "discography_manual_lock")
