"""track_embeddings table for content-based ANN.

Stores opaque dense embeddings produced by the audio-feature
pipeline outside of backend. Backend only persists and looks them
up; the model that produced them is intentionally not named here.

The ``embedding`` column uses JSON for cross-dialect storage. A
later migration may swap to ``pgvector`` for HNSW-indexed ANN at
scale; consumers must keep reading through ``EmbeddingRepository``
so the storage swap stays transparent.

Revision ID: 0091
Revises: 0090
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_embeddings",
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey(
                "tracks.id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column(
            "embedding",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "dim",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=False,
            server_default="v0",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_track_embeddings_model_version",
        "track_embeddings",
        ["model_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_embeddings_model_version",
        table_name="track_embeddings",
    )
    op.drop_table("track_embeddings")
