"""add track_upload_meta table

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_upload_meta",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("upload_ip", sa.String(45), nullable=True),
        sa.Column("upload_user_agent", sa.Text(), nullable=True),
        sa.Column(
            "upload_telegram_data",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("track_upload_meta")
