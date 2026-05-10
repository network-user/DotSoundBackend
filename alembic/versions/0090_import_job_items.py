"""import_job_items table for per-track import progress

Replaces the JSONB ``imported``/``not_matched`` lists inside
``import_jobs.tracks_data`` for the per-item state. Storing one
row per track lets a worker:

* update one item's status without rewriting the whole JSONB blob
  (cheap commits in the per-track loop);
* resume after a crash by skipping rows already in a terminal state
  (``done``/``failed``/``skipped``/``deduped``);
* project the API ``tracks_data.imported``/``not_matched`` shape
  on read without keeping the lists in memory between commits.

``status`` values:
    pending -- not processed yet
    done    -- imported (new track) or local match linked
    failed  -- error during search/match/import
    skipped -- pre-import filter rejected (file too large, ...)
    deduped -- linked to existing user track via blob hash

Revision ID: 0090
Revises: 0089
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_job_items",
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "track_id",
            sa.BigInteger(),
            sa.ForeignKey("tracks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "title",
            sa.String(length=512),
            nullable=True,
        ),
        sa.Column(
            "artist",
            sa.String(length=512),
            nullable=True,
        ),
        sa.Column(
            "sc_url",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "local_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("job_id", "idx"),
    )
    op.create_index(
        "ix_import_job_items_job_status",
        "import_job_items",
        ["job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_job_items_job_status",
        table_name="import_job_items",
    )
    op.drop_table("import_job_items")
