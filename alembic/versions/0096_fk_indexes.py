"""Add missing indexes on foreign-key columns.

The columns below are filtered on in list/search queries but had no
btree index, forcing sequential scans as row counts grow:

* ``tracks.album_id`` — ``list_by_album``, ``album_position`` sort.
* ``playlists.owner_id`` — ``list_by_owner`` paginated.
* ``albums.owner_id`` — ``list_by_owner`` paginated.
* ``conversations.created_by_id`` — admin/owner queries.
* ``messages.sender_id`` — user-sent-messages history.

All indexes are created with ``IF NOT EXISTS`` semantics via
``op.create_index`` so re-running on a hand-patched DB does not fail.

Revision ID: 0096
Revises: 0095
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_tracks_album_id", "tracks", "album_id"),
    ("ix_playlists_owner_id", "playlists", "owner_id"),
    ("ix_albums_owner_id", "albums", "owner_id"),
    (
        "ix_conversations_created_by_id",
        "conversations",
        "created_by_id",
    ),
    ("ix_messages_sender_id", "messages", "sender_id"),
)


def upgrade() -> None:
    for name, table, column in _INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name, _table, _column in _INDEXES:
        op.drop_index(name)
