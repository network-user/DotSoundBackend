from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.repositories.admin import AdminRepository

TimecodeSyncMode = Literal["unsynced", "resync_existing", "all"]


class AdminLyricsTimecodeSyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._admin = AdminRepository(session)

    def _with_text_stmt(
        self,
        *,
        has_sync: bool,
    ) -> Select[tuple[int]]:
        stripped = func.trim(func.coalesce(TrackLyrics.plain_text, ""))
        active_job_sq = exists(
            select(LyricsJob.id).where(
                LyricsJob.track_id == Track.id,
                LyricsJob.status.in_(("queued", "running")),
            ),
        )
        synced_present = self._admin._synced_lines_present()
        stmt = (
            select(Track.id)
            .join(
                TrackLyrics,
                TrackLyrics.track_id == Track.id,
            )
            .where(
                Track.is_active.is_(True),
                stripped != "",
                ~active_job_sq,
            )
        )
        return stmt.where(synced_present if has_sync else ~synced_present)

    def _unsynced_with_text_stmt(self) -> Select[tuple[int]]:
        return self._with_text_stmt(has_sync=False)

    def _resync_existing_stmt(self) -> Select[tuple[int]]:
        return self._with_text_stmt(has_sync=True)

    async def count_unsynced_candidates(self) -> int:
        stmt = select(func.count()).select_from(
            self._unsynced_with_text_stmt().subquery()
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_resync_candidates(self) -> int:
        stmt = select(func.count()).select_from(
            self._resync_existing_stmt().subquery()
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def candidate_counts(self) -> dict[str, int]:
        unsynced = await self.count_unsynced_candidates()
        resync_existing = await self.count_resync_candidates()
        return {
            "unsynced": unsynced,
            "resync_existing": resync_existing,
            "all": unsynced + resync_existing,
        }

    async def list_unsynced_track_ids(
        self,
        *,
        limit: int,
        track_ids: list[int] | None = None,
    ) -> list[int]:
        stmt = self._unsynced_with_text_stmt().order_by(
            TrackLyrics.updated_at.asc()
        )
        if track_ids:
            stmt = stmt.where(Track.id.in_(track_ids))
        stmt = stmt.limit(max(1, int(limit)))
        result = await self._session.execute(stmt)
        return [int(r) for r in result.scalars().all()]

    async def list_candidate_targets(
        self,
        *,
        mode: TimecodeSyncMode,
        limit: int,
        track_ids: list[int] | None = None,
    ) -> list[tuple[int, Literal["unsynced", "resync_existing"]]]:
        lim = max(1, int(limit))
        modes: tuple[Literal["unsynced", "resync_existing"], ...]
        if mode == "all":
            modes = ("unsynced", "resync_existing")
        elif mode == "resync_existing":
            modes = ("resync_existing",)
        else:
            modes = ("unsynced",)
        out: list[tuple[int, Literal["unsynced", "resync_existing"]]] = []
        seen: set[int] = set()
        for item_mode in modes:
            if len(out) >= lim:
                break
            stmt = (
                self._resync_existing_stmt()
                if item_mode == "resync_existing"
                else self._unsynced_with_text_stmt()
            ).order_by(TrackLyrics.updated_at.asc())
            if track_ids:
                stmt = stmt.where(Track.id.in_(track_ids))
            stmt = stmt.limit(lim - len(out))
            result = await self._session.execute(stmt)
            for track_id in result.scalars().all():
                tid = int(track_id)
                if tid in seen:
                    continue
                seen.add(tid)
                out.append((tid, item_mode))
        return out

    async def job_id_by_progress(
        self,
        progress_id: str,
    ) -> str | None:
        result = await self._session.execute(
            select(LyricsJob.id).where(LyricsJob.progress_id == progress_id)
        )
        row = result.scalar_one_or_none()
        return str(row) if row is not None else None

    async def list_align_jobs(
        self,
        *,
        limit: int = 200,
        requested_by_user_id: int | None = None,
        since: datetime | None = None,
    ) -> list[LyricsJob]:
        sm = max(1, min(500, int(limit)))
        queue_rank = case(
            (LyricsJob.status == "queued", 0),
            (LyricsJob.status == "running", 1),
            else_=2,
        )
        stmt = select(LyricsJob).where(
            LyricsJob.request_align_existing_text.is_(True)
        )
        if requested_by_user_id is not None:
            stmt = stmt.where(
                LyricsJob.requested_by_user_id == requested_by_user_id
            )
        if since is not None:
            stmt = stmt.where(LyricsJob.created_at >= since)
        stmt = stmt.order_by(
            queue_rank.asc(),
            LyricsJob.queue_priority.desc(),
            LyricsJob.created_at.asc(),
        ).limit(sm)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_align_job(self, job_id: str) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(
                LyricsJob.id == job_id,
                LyricsJob.request_align_existing_text.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def max_queued_align_priority(self) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(LyricsJob.queue_priority), 0))
            .select_from(LyricsJob)
            .where(
                LyricsJob.request_align_existing_text.is_(True),
                LyricsJob.status == "queued",
            )
        )
        return int(result.scalar_one() or 0)

    async def track_labels(
        self, track_ids: list[int]
    ) -> dict[int, dict[str, str | None]]:
        if not track_ids:
            return {}
        result = await self._session.execute(
            select(Track.id, Track.title, Track.artist).where(
                Track.id.in_(track_ids)
            )
        )
        return {
            int(row.id): {
                "title": row.title,
                "artist": row.artist,
            }
            for row in result.all()
        }
