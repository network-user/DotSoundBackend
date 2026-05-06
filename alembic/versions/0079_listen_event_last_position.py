"""listen_events.last_position_seconds for resume

Add ``last_position_seconds`` to ``listen_events`` so that the
"continue listening" experience can resume a track at the second
where the user left off, across devices and reloads. Default
is ``0`` (legacy events keep current behaviour).

Revision ID: 0079
Revises: 0078
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listen_events",
        sa.Column(
            "last_position_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "listen_events", "last_position_seconds"
    )
