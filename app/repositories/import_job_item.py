from __future__ import annotations

from collections.abc import Callable

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Insert

from app.models.import_job_item import ImportJobItem

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _insert_dialect(
    session: AsyncSession,
) -> Callable[..., Insert]:
    bind = session.get_bind()
    name = getattr(bind.dialect, "name", "")
    if name == "postgresql":
        return pg_insert  # type: ignore[return-value]
    return sqlite_insert  # type: ignore[return-value]


class ImportJobItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seed_pending(self, job_id: int, items: list[dict]) -> None:
        """Insert one ``pending`` row per selected item, idempotent on resume.

        Called once at worker start. ``ON CONFLICT DO NOTHING``
        keeps a re-entrant worker (after a sweeper reset) from
        resetting items already in a terminal state.
        """
        if not items:
            return
        rows = [
            {
                "job_id": job_id,
                "idx": idx,
                "status": "pending",
                "title": (item.get("title") or "")[:512] or None,
                "artist": (item.get("artist") or "")[:512] or None,
            }
            for idx, item in enumerate(items)
        ]
        insert = _insert_dialect(self._session)
        stmt = (
            insert(ImportJobItem)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["job_id", "idx"])
        )
        await self._session.execute(stmt)

    async def list_pending_indices(self, job_id: int) -> list[int]:
        result = await self._session.execute(
            select(ImportJobItem.idx)
            .where(
                ImportJobItem.job_id == job_id,
                ImportJobItem.status == "pending",
            )
            .order_by(ImportJobItem.idx.asc())
        )
        return [int(r[0]) for r in result.all()]

    async def mark_done(
        self,
        job_id: int,
        idx: int,
        *,
        track_id: int | None,
        title: str | None,
        artist: str | None,
        sc_url: str | None,
        local_match: bool,
    ) -> None:
        await self._session.execute(
            update(ImportJobItem)
            .where(
                ImportJobItem.job_id == job_id,
                ImportJobItem.idx == idx,
            )
            .values(
                status="done",
                track_id=track_id,
                title=(title or "")[:512] or None,
                artist=(artist or "")[:512] or None,
                sc_url=sc_url,
                local_match=local_match,
                reason=None,
            )
        )

    async def mark_failed(
        self,
        job_id: int,
        idx: int,
        *,
        title: str | None,
        artist: str | None,
        reason: str,
    ) -> None:
        await self._session.execute(
            update(ImportJobItem)
            .where(
                ImportJobItem.job_id == job_id,
                ImportJobItem.idx == idx,
            )
            .values(
                status="failed",
                title=(title or "")[:512] or None,
                artist=(artist or "")[:512] or None,
                reason=(reason or "")[:255] or None,
            )
        )

    async def mark_skipped(
        self,
        job_id: int,
        idx: int,
        *,
        title: str | None,
        reason: str,
    ) -> None:
        await self._session.execute(
            update(ImportJobItem)
            .where(
                ImportJobItem.job_id == job_id,
                ImportJobItem.idx == idx,
            )
            .values(
                status="skipped",
                title=(title or "")[:512] or None,
                reason=(reason or "")[:255] or None,
            )
        )

    async def mark_deduped(
        self,
        job_id: int,
        idx: int,
        *,
        track_id: int,
        title: str | None,
    ) -> None:
        await self._session.execute(
            update(ImportJobItem)
            .where(
                ImportJobItem.job_id == job_id,
                ImportJobItem.idx == idx,
            )
            .values(
                status="deduped",
                track_id=track_id,
                title=(title or "")[:512] or None,
                reason=None,
            )
        )

    async def counters(self, job_id: int) -> dict[str, int]:
        """Return ``{status: count}`` for the job."""
        result = await self._session.execute(
            select(ImportJobItem.status, func.count())
            .where(ImportJobItem.job_id == job_id)
            .group_by(ImportJobItem.status)
        )
        out: dict[str, int] = {}
        for status_v, n in result.all():
            out[str(status_v)] = int(n)
        return out

    async def list_for_response(
        self, job_id: int
    ) -> tuple[list[dict], list[dict]]:
        """Project items into the legacy ``imported``/``not_matched`` shape.

        Used by ``/import/{job_id}/status`` to keep the API stable
        while the persistence moved to a relational table.
        """
        result = await self._session.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job_id)
            .order_by(ImportJobItem.idx.asc())
        )
        imported: list[dict] = []
        not_matched: list[dict] = []
        for row in result.scalars().all():
            if row.status in ("done", "deduped"):
                payload: dict = {
                    "title": row.title,
                    "artist": row.artist,
                    "track_id": row.track_id,
                    "sc_url": row.sc_url,
                    "status": "done" if row.status == "done" else "deduped",
                }
                if row.local_match:
                    payload["local_match"] = True
                imported.append(payload)
            elif row.status in ("failed", "skipped"):
                not_matched.append(
                    {
                        "title": row.title,
                        "artist": row.artist,
                        "reason": row.reason or row.status,
                    }
                )
        return imported, not_matched
