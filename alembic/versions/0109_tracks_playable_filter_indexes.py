"""Indexes to speed up the playable-filter query on tracks.

The ``_playable_filter`` predicate used in every recommendation
candidate pool is:

    file_key IS NOT NULL
    OR access_mode IN ('third_party_stream', 'official_embed')

Without dedicated indexes PostgreSQL must do a sequential scan of the
tracks table for every candidate pool query.  Two partial indexes cover
both branches of the OR:

* ``ix_tracks_file_key_not_null`` — partial, ``WHERE file_key IS NOT NULL``
* ``ix_tracks_access_mode`` — plain btree on ``access_mode`` (low
  cardinality, but still helps the planner avoid a full seqscan for the
  IN-list branch)

Revision ID: 0109
Revises: 0108
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0109"
down_revision: str | None = "0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tracks_file_key_not_null",
        "tracks",
        ["file_key"],
        postgresql_where=sa.text("file_key IS NOT NULL"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_tracks_access_mode",
        "tracks",
        ["access_mode"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_access_mode",
        table_name="tracks",
        if_exists=True,
    )
    op.drop_index(
        "ix_tracks_file_key_not_null",
        table_name="tracks",
        if_exists=True,
    )
