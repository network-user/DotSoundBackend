"""legal compliance

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "source_url", sa.Text, nullable=True
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "source_name",
            sa.String(50),
            nullable=True,
        ),
    )
    op.add_column(
        "complaints",
        sa.Column(
            "reason_type",
            sa.String(30),
            server_default="other",
            nullable=False,
        ),
    )
    op.add_column(
        "complaints",
        sa.Column(
            "rightsholder_name",
            sa.String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "complaints",
        sa.Column(
            "proof_url", sa.Text, nullable=True
        ),
    )

    op.execute(
        "UPDATE tracks SET source_url = sc_url, "
        "source_name = 'SoundCloud' "
        "WHERE source = 'soundcloud' "
        "AND sc_url IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("complaints", "proof_url")
    op.drop_column(
        "complaints", "rightsholder_name"
    )
    op.drop_column("complaints", "reason_type")
    op.drop_column("tracks", "source_name")
    op.drop_column("tracks", "source_url")
