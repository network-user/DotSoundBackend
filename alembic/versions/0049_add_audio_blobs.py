"""add audio_blobs and track blob_id for CAS deduplication

Revision ID: 0049
Revises: 0048
Create Date: 2026-04-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def _partial_uq_where() -> str:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return "blob_id IS NOT NULL AND is_active = 1"
    return "blob_id IS NOT NULL AND is_active IS TRUE"


def upgrade() -> None:
    op.create_table(
        "audio_blobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ref_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_audio_blobs_content_sha256",
        "audio_blobs",
        ["content_sha256"],
        unique=True,
    )
    op.add_column(
        "tracks",
        sa.Column("blob_id", sa.Integer, nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "blob_ref_freed",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_tracks_blob_id_audio_blobs",
        "tracks",
        "audio_blobs",
        ["blob_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tracks_blob_id", "tracks", ["blob_id"])
    op.execute(
        f"CREATE UNIQUE INDEX uq_tracks_user_blob_active "
        f"ON tracks (uploaded_by_id, blob_id) WHERE ({_partial_uq_where()})"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_tracks_user_blob_active")
    op.drop_index("ix_tracks_blob_id", table_name="tracks")
    op.drop_constraint(
        "fk_tracks_blob_id_audio_blobs", "tracks", type_="foreignkey"
    )
    op.drop_column("tracks", "blob_ref_freed")
    op.drop_column("tracks", "blob_id")
    op.drop_index("ix_audio_blobs_content_sha256", table_name="audio_blobs")
    op.drop_table("audio_blobs")
