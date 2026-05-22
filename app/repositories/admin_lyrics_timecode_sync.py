from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.repositories.admin import AdminRepository


class AdminLyricsTimecodeSyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._admin = AdminRepository(session)

    def _unsynced_with_text_stmt(self) -> Select[tuple[int]]:
        stripped = func.trim(
            func.coalesce(TrackLyrics.plain_text, "")
        )
        active_job_sq = exists(
            select(LyricsJob.id).where(
                LyricsJob.track_id == Track.id,
                LyricsJob.status.in_(("queued", "running")),
            ),
        )
        return (
            select(Track.id)
            .join(
                TrackLyrics,
                TrackLyrics.track_id == Track.id,
            )
            .where(
                Track.is_active.is_(True),
                stripped != "",
                ~self._admin._synced_lines_present(),
                ~active_job_sq,
            )
        )

    async def count_unsynced_candidates(self) -> int:
        stmt = select(func.count()).select_from(
            self._unsynced_with_text_stmt().subquery()
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

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
                LyricsJob.requested_by_user_id
                == requested_by_user_id
            )
        if since is not None:
            stmt = stmt.where(LyricsJob.created_at >= since)
        stmt = (
            stmt.order_by(
                queue_rank.asc(),
                LyricsJob.queue_priority.desc(),
                LyricsJob.created_at.asc(),
            )
            .limit(sm)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_align_job(
        self, job_id: str
    ) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(
                LyricsJob.id == job_id,
                LyricsJob.request_align_existing_text.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def max_queued_align_priority(self) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(LyricsJob.queue_priority), 0)).where(
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
