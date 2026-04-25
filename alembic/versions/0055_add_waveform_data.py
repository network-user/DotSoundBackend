"""add waveform_data to tracks

Revision ID: 0055
Revises: 0054
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "waveform_data",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "waveform_data")
