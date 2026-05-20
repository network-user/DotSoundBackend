"""Add pg_trgm GIN indexes for substring search on names/titles.

Search by partial substring uses ``ILIKE '%foo%'`` on
``artists.name_normalized``, ``tracks.title``, ``playlists.name`` and
``albums.title``. Plain B-tree indexes do not help these patterns
(the leading ``%`` prevents prefix matching), so the planner falls
back to a sequential scan once the table grows.

A GIN index with the ``gin_trgm_ops`` opclass from the ``pg_trgm``
extension makes ``ILIKE '%foo%'`` and PostgreSQL's similarity
operators index-driven. Indexes are created with ``IF NOT EXISTS``
so the migration is idempotent on shared environments.

Note for ops: this migration runs as a regular DDL (no
``CONCURRENTLY``) which acquires a brief table lock per CREATE INDEX.
On large tables you may prefer to skip this revision and instead run
``CREATE INDEX CONCURRENTLY ... USING gin (... gin_trgm_ops);`` from
a maintenance window, then ``alembic stamp 0115`` afterwards.

Revision ID: 0115
Revises: 0114
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0115"
down_revision: str | None = "0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_artists_name_normalized_trgm", "artists", "name_normalized"),
    ("ix_tracks_title_trgm", "tracks", "title"),
    ("ix_playlists_name_trgm", "playlists", "name"),
    ("ix_albums_title_trgm", "albums", "title"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in _INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} USING gin "
            f"({column_name} gin_trgm_ops)"
        )


def downgrade() -> None:
    for index_name, _, _ in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
