"""Indexes for hot track/like/playlist/listen_events queries [BE-2, BE-5].

Feed, search and library-listing queries repeatedly filter tracks on
the same two flags before sorting, and the planner has no way to
avoid a sequential scan of ``tracks`` for either sort without a
matching partial index:

* ``ix_tracks_active_public_play_count`` -- partial btree on
  ``play_count`` ``WHERE is_active AND is_public``. Covers the
  ``play_count DESC, id DESC`` keyset ordering used by
  ``TrackRepository.search`` and ``.search_cursor``.
* ``ix_tracks_active_public_created_at`` -- partial btree on
  ``created_at`` with the same condition. Covers the main feed
  (``TrackRepository.list_active``) and the ``created_at DESC``
  prev/next lookups in ``get_adjacent`` / ``get_next_tracks``.
* ``ix_tracks_uploaded_by_created`` -- plain composite on
  ``(uploaded_by_id, created_at)``. Covers "my uploads" listings
  (``list_by_user`` / ``list_public_by_user``), which filter by
  owner and sort by upload time; not partial since ``list_by_user``
  intentionally includes the owner's private tracks too.

Two more close a PK-doesn't-help gap on ``likes``: its primary key is
``(user_id, track_id)``, which cannot serve a ``track_id``-only
lookup or a per-user listing ordered by time.

* ``ix_likes_track_id`` -- ``LikeRepository.count_for_track`` filters
  by ``track_id`` alone; ``track_id`` is the non-leading PK column so
  the existing PK index can't be used.
* ``ix_likes_user_created`` -- composite on ``(user_id, created_at)``.
  Covers the default newest-first ordering in
  ``list_liked_tracks`` / ``list_liked_queue`` (``_apply_sort``),
  which the PK alone can't satisfy without an extra sort step.

Same PK-prefix gap on ``playlist_tracks`` (PK
``(playlist_id, track_id)``) for the reverse "which playlists saved
this track" lookup used by the recsys unique-savers signal:

* ``ix_playlist_tracks_track_id`` -- covers
  ``RecommendationRepository.get_unique_savers_per_track``, which
  filters ``PlaylistTrack.track_id.in_(track_ids)`` with no
  ``playlist_id`` predicate.

Finally, the daily retention worker for ``listen_events``
(``app/services/event_aggregation_worker.py``, raw SQL, not routed
through a repository) scans and deletes raw rows purely by
``created_at`` range once a day. Neither existing composite index
(``user_id, created_at`` / ``track_id, created_at``) has
``created_at`` as its leading column, so that sweep seq-scans the
whole table once it grows past the retention window:

* ``ix_listen_events_created_at`` -- plain btree on ``created_at``.
  Covers the worker's cutoff scan (``WHERE created_at < :cutoff``)
  and per-day aggregate/delete range scans
  (``WHERE created_at >= :day_start AND created_at < :day_end``).

Every index is built with ``CREATE INDEX CONCURRENTLY`` inside an
``autocommit_block`` (``CONCURRENTLY`` is incompatible with running
inside a transaction), so these online tables are not write-locked
for the duration of the build. Note: if a concurrent build is
interrupted (crash, lock timeout, cancelled statement) Postgres can
leave an INVALID index behind; drop it manually before re-running,
otherwise ``IF NOT EXISTS`` skips the rebuild and keeps the unusable
index.

Revision ID: 0121
Revises: 0120
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0121"
down_revision: str | None = "0120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CONCURRENTLY cannot run in a transaction: build each index in an
    # autocommit block so writes to these hot tables keep flowing.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_tracks_active_public_play_count",
            "tracks",
            ["play_count"],
            postgresql_where=sa.text("is_active AND is_public"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_tracks_active_public_created_at",
            "tracks",
            ["created_at"],
            postgresql_where=sa.text("is_active AND is_public"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_tracks_uploaded_by_created",
            "tracks",
            ["uploaded_by_id", "created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_likes_track_id",
            "likes",
            ["track_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_likes_user_created",
            "likes",
            ["user_id", "created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_playlist_tracks_track_id",
            "playlist_tracks",
            ["track_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_listen_events_created_at",
            "listen_events",
            ["created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    # DROP INDEX CONCURRENTLY also cannot run in a transaction.
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_listen_events_created_at",
            table_name="listen_events",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_playlist_tracks_track_id",
            table_name="playlist_tracks",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_likes_user_created",
            table_name="likes",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_likes_track_id",
            table_name="likes",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_tracks_uploaded_by_created",
            table_name="tracks",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_tracks_active_public_created_at",
            table_name="tracks",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_tracks_active_public_play_count",
            table_name="tracks",
            postgresql_concurrently=True,
            if_exists=True,
        )
