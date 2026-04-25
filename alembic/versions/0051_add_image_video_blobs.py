"""add image_blobs and video_blobs tables for CAS deduplication

Revision ID: 0051
Revises: 0050
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_blobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "ref_count", sa.Integer(), server_default="0", nullable=False
        ),
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
        "ix_image_blobs_content_sha256",
        "image_blobs",
        ["content_sha256"],
        unique=True,
    )

    op.create_table(
        "video_blobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "ref_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("thumbnail_blob_id", sa.Integer, nullable=True),
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
        "ix_video_blobs_content_sha256",
        "video_blobs",
        ["content_sha256"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_video_blobs_thumbnail_blob_id",
        "video_blobs",
        "image_blobs",
        ["thumbnail_blob_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "tracks",
        sa.Column("cover_blob_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_tracks_cover_blob_id",
        "tracks",
        "image_blobs",
        ["cover_blob_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tracks_cover_blob_id", "tracks", ["cover_blob_id"])

    op.add_column(
        "tracks",
        sa.Column("video_blob_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_tracks_video_blob_id",
        "tracks",
        "video_blobs",
        ["video_blob_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tracks_video_blob_id", "tracks", ["video_blob_id"])

    op.add_column(
        "users",
        sa.Column("avatar_blob_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_users_avatar_blob_id",
        "users",
        "image_blobs",
        ["avatar_blob_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_avatar_blob_id", "users", type_="foreignkey")
    op.drop_column("users", "avatar_blob_id")

    op.drop_index("ix_tracks_video_blob_id", table_name="tracks")
    op.drop_constraint(
        "fk_tracks_video_blob_id", "tracks", type_="foreignkey"
    )
    op.drop_column("tracks", "video_blob_id")

    op.drop_index("ix_tracks_cover_blob_id", table_name="tracks")
    op.drop_constraint(
        "fk_tracks_cover_blob_id", "tracks", type_="foreignkey"
    )
    op.drop_column("tracks", "cover_blob_id")

    op.drop_constraint(
        "fk_video_blobs_thumbnail_blob_id", "video_blobs", type_="foreignkey"
    )
    op.drop_index("ix_video_blobs_content_sha256", table_name="video_blobs")
    op.drop_table("video_blobs")

    op.drop_index("ix_image_blobs_content_sha256", table_name="image_blobs")
    op.drop_table("image_blobs")
