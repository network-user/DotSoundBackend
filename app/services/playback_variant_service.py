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
        platforms = list(EXTERNAL_SOURCE_PLATFORM_ORDER)
        found = await self._tracks.find_variants_by_title_and_duration(
            title,
            dur,
            platforms=platforms,
            tolerance_pct=tol,
            limit=5 * max(1, len(platforms)),
        )
        for c in found:
            if c.id != track.id and self._artist_compatible(
                track.artist,
                c.artist,
            ):
                ids.add(c.id)

        return sorted(ids)

    async def resolve_variant_track_ids_batch(
        self,
        tracks: list[Track],
    ) -> dict[int, list[int]]:
        """Resolve variant ids for many tracks with sequential DB I/O.

        Semantics are 1:1 with :meth:`resolve_variant_track_ids` for
        every track, but composition-group members are fetched in a
        single query and no statement runs concurrently. Callers can
        then fan out CPU-only work over the shared session without
        tripping SQLAlchemy's one-statement-per-session rule.
        """
        if not tracks:
            return {}

        group_ids = {
            t.composition_group_id for t in tracks if t.composition_group_id
        }
        members_by_group: dict[str, set[int]] = {}
        if group_ids:
            result = await self._session.execute(
                select(Track.id, Track.composition_group_id).where(
                    Track.composition_group_id.in_(group_ids),
                    Track.is_active.is_(True),
                    Track.is_public.is_(True),
                )
            )
            for row in result.all():
                gid = row[1]
                if gid is None:
                    continue
                members_by_group.setdefault(gid, set()).add(row[0])

        resolved: dict[int, list[int]] = {}
        for track in tracks:
            if track.id in resolved:
                continue
            group_id = track.composition_group_id
            if group_id:
                members = set(members_by_group.get(group_id, set()))
                members.add(track.id)
                resolved[track.id] = sorted(members)
            else:
                resolved[track.id] = await self.resolve_variant_track_ids(
                    track
                )
        return resolved

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
