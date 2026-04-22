"""Find and merge duplicate Track rows before applying UNIQUE constraints.

Identifies duplicates by ``sc_url`` and by
``(imported_from, external_id)``, picks the lowest-id row in each
connected component as canonical, redirects every foreign-key
reference from duplicates to canonical, then deletes the duplicate
Track rows. Composite-PK and unique-per-track child tables get
conflict handling so we never violate an existing constraint while
merging.

Idempotent: dry-run by default (the transaction is rolled back).
Pass ``--apply`` to commit the changes.

Usage::

    poetry run python scripts/dedupe_tracks.py
    poetry run python scripts/dedupe_tracks.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import (  # noqa: E402, I001
    AsyncSessionLocal,
    dispose_engine,
)

_PLAIN_FK_TABLES: tuple[tuple[str, str], ...] = (
    ("complaints", "track_id"),
    ("listen_events", "track_id"),
    ("comments", "track_id"),
    ("lyrics_jobs", "track_id"),
    ("search_events", "clicked_track_id"),
    ("messages", "shared_track_id"),
)


_COMPOSITE_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("likes", "track_id", ("user_id",)),
    ("dislikes", "track_id", ("user_id",)),
    ("playlist_tracks", "track_id", ("playlist_id",)),
    ("track_artists", "track_id", ("artist_id",)),
)


_UNIQUE_PER_TRACK_TABLES: tuple[tuple[str, str], ...] = (
    ("track_lyrics", "track_id"),
    ("track_info", "track_id"),
    ("track_upload_meta", "track_id"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge duplicate tracks (by sc_url and by "
            "(imported_from, external_id)) into the lowest-id "
            "canonical row, redirecting all FK references."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Commit the changes. Default is dry-run "
            "(the transaction is rolled back)."
        ),
    )
    return parser.parse_args()


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        if x not in self._parent:
            self._parent[x] = x
            return x
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        cur = x
        while self._parent[cur] != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if ra < rb:
            self._parent[rb] = ra
        else:
            self._parent[ra] = rb

    def members(self) -> list[int]:
        return list(self._parent)


async def _build_merge_plan(
    session: AsyncSession,
) -> dict[int, list[int]]:
    """Return mapping ``canonical_id -> [duplicate ids]``."""
    uf = _UnionFind()

    sc_rows = (
        await session.execute(
            text(
                "SELECT sc_url, ARRAY_AGG(id ORDER BY id) AS ids "
                "FROM tracks "
                "WHERE sc_url IS NOT NULL "
                "GROUP BY sc_url "
                "HAVING COUNT(*) > 1"
            )
        )
    ).all()
    for _sc_url, ids in sc_rows:
        for other in ids[1:]:
            uf.union(ids[0], other)

    ext_rows = (
        await session.execute(
            text(
                "SELECT imported_from, external_id, "
                "ARRAY_AGG(id ORDER BY id) AS ids "
                "FROM tracks "
                "WHERE external_id IS NOT NULL "
                "AND imported_from IS NOT NULL "
                "GROUP BY imported_from, external_id "
                "HAVING COUNT(*) > 1"
            )
        )
    ).all()
    for _imported_from, _external_id, ids in ext_rows:
        for other in ids[1:]:
            uf.union(ids[0], other)

    plan: dict[int, list[int]] = defaultdict(list)
    for tid in uf.members():
        root = uf.find(tid)
        if root != tid:
            plan[root].append(tid)
    return dict(plan)


async def _merge_one(
    session: AsyncSession,
    canonical: int,
    dup: int,
) -> dict[str, int]:
    """Move every FK reference from ``dup`` to ``canonical`` then
    drop the duplicate Track row.

    Returns a per-table count of affected rows for reporting.
    """
    counts: dict[str, int] = {}
    params = {"canonical": canonical, "dup": dup}

    for table, col in _PLAIN_FK_TABLES:
        result = await session.execute(
            text(
                f"UPDATE {table} SET {col} = :canonical " f"WHERE {col} = :dup"
            ),
            params,
        )
        if result.rowcount:
            counts[f"{table}.{col}"] = result.rowcount

    for table, track_col, other_cols in _COMPOSITE_TABLES:
        cols_csv = ", ".join(other_cols)
        del_result = await session.execute(
            text(
                f"DELETE FROM {table} "
                f"WHERE {track_col} = :dup "
                f"AND ({cols_csv}) IN ("
                f"  SELECT {cols_csv} FROM {table} "
                f"  WHERE {track_col} = :canonical"
                f")"
            ),
            params,
        )
        if del_result.rowcount:
            counts[f"{table}.{track_col}.del"] = del_result.rowcount
        upd_result = await session.execute(
            text(
                f"UPDATE {table} SET {track_col} = :canonical "
                f"WHERE {track_col} = :dup"
            ),
            params,
        )
        if upd_result.rowcount:
            counts[f"{table}.{track_col}"] = upd_result.rowcount

    for table, track_col in _UNIQUE_PER_TRACK_TABLES:
        canon_exists = (
            await session.execute(
                text(
                    f"SELECT 1 FROM {table} "
                    f"WHERE {track_col} = :canonical "
                    f"LIMIT 1"
                ),
                {"canonical": canonical},
            )
        ).scalar()
        if canon_exists:
            del_result = await session.execute(
                text(f"DELETE FROM {table} " f"WHERE {track_col} = :dup"),
                {"dup": dup},
            )
            if del_result.rowcount:
                counts[f"{table}.{track_col}.del"] = del_result.rowcount
        else:
            upd_result = await session.execute(
                text(
                    f"UPDATE {table} SET {track_col} = :canonical "
                    f"WHERE {track_col} = :dup"
                ),
                params,
            )
            if upd_result.rowcount:
                counts[f"{table}.{track_col}"] = upd_result.rowcount

    track_del = await session.execute(
        text("DELETE FROM tracks WHERE id = :dup"),
        {"dup": dup},
    )
    if track_del.rowcount:
        counts["tracks.id"] = track_del.rowcount
    return counts


async def _run() -> int:
    args = _parse_args()
    apply = bool(args.apply)
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== dedupe_tracks ({mode}) ===")

    try:
        async with AsyncSessionLocal() as session:
            plan = await _build_merge_plan(session)
            if not plan:
                print("No duplicates found. Nothing to do.")
                return 0

            total_dups = sum(len(v) for v in plan.values())
            print(
                f"Found {len(plan)} duplicate group(s), "
                f"{total_dups} duplicate row(s) total."
            )

            for canonical in sorted(plan):
                dups = sorted(plan[canonical])
                print(
                    f"\n[group canonical={canonical}] "
                    f"merging {len(dups)} duplicate(s): {dups}"
                )
                for dup in dups:
                    counts = await _merge_one(session, canonical, dup)
                    if counts:
                        for k, v in counts.items():
                            print(f"  - {k}: {v}")
                    else:
                        print(f"  - dup={dup} had no FK refs")

            if apply:
                await session.commit()
                print("\nCommitted.")
            else:
                await session.rollback()
                print(
                    "\nDRY-RUN - rolled back. "
                    "Re-run with --apply to commit."
                )
        return 0
    finally:
        await dispose_engine()


def main() -> None:
    code = asyncio.run(_run())
    sys.exit(code)


if __name__ == "__main__":
    main()
