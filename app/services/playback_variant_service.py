from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository
from dotsound_private_core.services.playback_variant_policy import (
    catalog_rank,
    external_platform_rank,
    title_duration_match_tolerance_pct,
    EXTERNAL_SOURCE_PLATFORM_ORDER,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlaybackVariantService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracks = TrackRepository(session)

    @staticmethod
    def _artist_compatible(
        left: str | None,
        right: str | None,
    ) -> bool:
        if not left or not right:
            return True
        a = left.strip().lower()
        b = right.strip().lower()
        if a == b:
            return True
        return a in b or b in a

    async def resolve_variant_track_ids(self, track: Track) -> list[int]:
        if track.composition_group_id:
            result = await self._session.execute(
                select(Track.id).where(
                    Track.composition_group_id == track.composition_group_id,
                    Track.is_active.is_(True),
                    Track.is_public.is_(True),
                )
            )
            out = {row[0] for row in result.all()}
            out.add(track.id)
            return sorted(out)

        ids: set[int] = {track.id}
        if not (track.title and track.duration_seconds):
            return [track.id]

        title = track.title.strip()
        if not title:
            return [track.id]

        dur = int(track.duration_seconds)
        tol = title_duration_match_tolerance_pct()
        current_pf = (track.source_platform or "").strip().lower()

        for pf in EXTERNAL_SOURCE_PLATFORM_ORDER:
            if pf == current_pf:
                continue
            found = await self._tracks.find_by_title_and_duration(
                title,
                dur,
                platform=pf,
                tolerance_pct=tol,
                limit=5,
            )
            for c in found:
                if c.id != track.id and self._artist_compatible(
                    track.artist,
                    c.artist,
                ):
                    ids.add(c.id)

        if current_pf in EXTERNAL_SOURCE_PLATFORM_ORDER:
            found_same = await self._tracks.find_by_title_and_duration(
                title,
                dur,
                platform=current_pf,
                tolerance_pct=tol,
                limit=5,
            )
            for c in found_same:
                if c.id != track.id and self._artist_compatible(
                    track.artist,
                    c.artist,
                ):
                    ids.add(c.id)

        return sorted(ids)

    def pick_primary_track(self, tracks: list[Track]) -> Track:
        if len(tracks) == 1:
            return tracks[0]
        return sorted(
            tracks,
            key=lambda t: (
                catalog_rank(t.catalog_type),
                external_platform_rank(t.source_platform),
                -(t.play_count or 0),
                t.id,
            ),
        )[0]

    async def dedupe_track_rows_for_display(
        self,
        tracks: list[Track],
    ) -> list[Track]:
        if not tracks:
            return []
        emitted: set[frozenset[int]] = set()
        out: list[Track] = []
        for t in tracks:
            group = frozenset(await self.resolve_variant_track_ids(t))
            if group in emitted:
                continue
            emitted.add(group)
            rows = await self._tracks.get_by_ids_preserve_order(
                sorted(group),
            )
            active = [r for r in rows if r.is_active and r.is_public]
            if not active:
                continue
            pick = self.pick_primary_track(active)
            out.append(pick)
        return out
