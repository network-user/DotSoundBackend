"""add import_jobs table

Revision ID: 0011
Revises: 0010_lyrics_follows_albums
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source", sa.String(50), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="scanning",
        ),
        sa.Column(
            "total_tracks",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "completed_tracks",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "failed_tracks",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column("tracks_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
