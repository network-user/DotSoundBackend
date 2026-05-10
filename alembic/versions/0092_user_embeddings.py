"""user_embeddings table for two-tower retrieval.

Stores learned per-user taste vectors produced by an opaque
trainer outside backend. The eventual swap to ``pgvector`` for
HNSW-indexed user-track matching is transparent because backend
reads through ``EmbeddingRepository``.

Revision ID: 0092
Revises: 0091
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_embeddings",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", sa.JSON(), nullable=True),
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
        "ix_user_embeddings_model_version",
        "user_embeddings",
        ["model_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_embeddings_model_version",
        table_name="user_embeddings",
    )
    op.drop_table("user_embeddings")
