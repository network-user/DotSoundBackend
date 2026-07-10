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
    op.execute(_DEDUP_SQL)
    op.create_index(
        "uq_complaints_reported_by_user_track",
        "complaints",
        ["reported_by_user_id", "track_id"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_complaints_reported_by_user_track",
        table_name="complaints",
        if_exists=True,
    )
