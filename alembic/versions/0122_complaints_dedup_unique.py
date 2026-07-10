"""Dedup complaints and enforce one report per (user, track) [BE-7].

``complaints.track_id`` is ``NOT NULL`` (complaints only ever target
a track -- there is no other reportable entity in this schema), so
the new unique index does not need a partial ``WHERE`` clause.

Before the unique index can be created, any existing duplicate
``(reported_by_user_id, track_id)`` rows must be collapsed to one.
The dedup keeps the earliest report per pair (by ``created_at``, ties
broken by ``id``) and deletes the rest via a ``ROW_NUMBER()`` window
query, same idiom as the ``album_position`` backfill in revision
0071.

Downgrade drops the unique index but cannot undo the dedup DELETE --
rows removed by ``upgrade()`` are gone for good. That's an accepted,
one-way cleanup: the deleted rows were true duplicates (same user,
same track), so nothing of value is lost.

The dedup DELETE runs transactionally in the migration's own
transaction, *before* the ``autocommit_block``; the unique index is
then built with ``CREATE UNIQUE INDEX CONCURRENTLY`` inside that block
(``CONCURRENTLY`` is incompatible with a transaction), so ``complaints``
is not write-locked while the index builds. Note: an interrupted
concurrent build can leave an INVALID index behind; drop it manually
before re-running, otherwise ``IF NOT EXISTS`` skips the rebuild and
keeps the unusable index.

Revision ID: 0122
Revises: 0121
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0122"
down_revision: str | None = "0121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEDUP_SQL = text(
    """
    DELETE FROM complaints c
    USING (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY reported_by_user_id, track_id
                   ORDER BY created_at ASC, id ASC
               ) AS rn
        FROM complaints
    ) AS ranked
    WHERE c.id = ranked.id
      AND ranked.rn > 1
    """
)


def upgrade() -> None:
    # Collapse duplicates transactionally FIRST, in the migration's own
    # transaction, so the DELETE is atomic.
    op.execute(_DEDUP_SQL)
    # Then build the unique index CONCURRENTLY, which cannot run inside
    # a transaction, in an autocommit block.
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_complaints_reported_by_user_track",
            "complaints",
            ["reported_by_user_id", "track_id"],
            unique=True,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    # DROP INDEX CONCURRENTLY also cannot run in a transaction.
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_complaints_reported_by_user_track",
            table_name="complaints",
            postgresql_concurrently=True,
            if_exists=True,
        )
