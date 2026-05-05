"""genre mix overrides

Revision ID: 0073
Revises: 0072
Create Date: 2026-05-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genre_mix_overrides",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "genre",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "title",
            sa.String(length=256),
            nullable=False,
        ),
        sa.Column(
            "track_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "updated_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_genre_mix_overrides_genre",
        "genre_mix_overrides",
        ["genre"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_genre_mix_overrides_genre",
        table_name="genre_mix_overrides",
    )
    op.drop_table("genre_mix_overrides")
