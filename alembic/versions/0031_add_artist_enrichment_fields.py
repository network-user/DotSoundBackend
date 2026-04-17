"""add artist enrichment fields for external artist metadata

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column("birth_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column("birthplace", sa.String(128), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column("country", sa.String(2), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column("website_url", sa.String(512), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column(
            "enrichment_status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "artists",
        sa.Column(
            "enriched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_artists_enrichment_status",
        "artists",
        ["enrichment_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_artists_enrichment_status",
        table_name="artists",
    )
    op.drop_column("artists", "enriched_at")
    op.drop_column("artists", "enrichment_status")
    op.drop_column("artists", "website_url")
    op.drop_column("artists", "country")
    op.drop_column("artists", "birthplace")
    op.drop_column("artists", "birth_date")
