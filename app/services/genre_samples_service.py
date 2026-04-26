from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.genre_sample import GenreSample
from app.models.track import Track
from app.models.track_preview_clip import TrackPreviewClip
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class GenreSamplesService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._track_repo = TrackRepository(session)

    @staticmethod
    def _curated_join_predicate():  # noqa: ANN205
        p = TrackRepository._genre_sample_track_predicate()
        return p

    async def get_preview_queue(self, genre: str, limit: int) -> list[Track]:
        cap = max(1, min(int(limit), 50))
        curated_rows = (
            await self._session.execute(
                select(GenreSample, Track)
                .join(Track, Track.id == GenreSample.track_id)
                .where(
                    GenreSample.genre == genre,
                    self._curated_join_predicate(),
                )
                .order_by(GenreSample.position, GenreSample.id)
            )
        ).all()
        out: list[Track] = []
        seen: set[int] = set()
        for _gs, tr in curated_rows:
            if tr.id in seen:
                continue
            if len(out) >= cap:
                break
            out.append(tr)
            seen.add(tr.id)
        need = cap - len(out)
        if need > 0:
            more = (
                await self._track_repo.list_by_genre_for_genre_sample_backfill(
                    genre,
                    exclude_ids=seen,
                    limit=need,
                )
            )
            out.extend(more)
        return out[:cap]

    async def ensure_preview_clip(self, track_id: int) -> TrackPreviewClip:
        row = await self._session.get(TrackPreviewClip, track_id)
        if row is not None:
            return row
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise ValueError("track not found or inactive")
        if track.blob_id is None or not track.file_key:
            raise ValueError("track has no blob for preview")
        d = track.duration_seconds
        if d is None or d <= 0:
            raise ValueError("track has no duration for preview")
        sec = min(15.0, float(d))
        clip = TrackPreviewClip(
            track_id=track_id,
            start_sec=0.0,
            duration_sec=sec,
            source="fixed_offset",
        )
        self._session.add(clip)
        await self._session.flush()
        return clip

    async def add_curated(
        self,
        genre: str,
        track_id: int,
        position: int = 0,
    ) -> GenreSample:
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise ValueError("track not found or inactive")
        if not self._is_eligible_for_sample(track):
            raise ValueError("track not eligible for genre sample")
        row = GenreSample(
            genre=genre,
            track_id=track_id,
            position=position,
            curated=True,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    @staticmethod
    def _is_eligible_for_sample(track: Track) -> bool:
        return bool(
            track.blob_id
            and track.file_key
            and track.is_active
            and track.is_public
            and track.duration_seconds
        )

    async def remove_curated(self, sample_id: int) -> bool:
        row = await self._session.get(GenreSample, sample_id)
        if row is None:
            return False
        await self._session.delete(row)
        return True

    async def list_curated(self, genre: str) -> list[GenreSample]:
        r = await self._session.execute(
            select(GenreSample)
            .where(GenreSample.genre == genre)
            .order_by(GenreSample.position, GenreSample.id)
        )
        return list(r.scalars().all())
