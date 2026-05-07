from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository
from app.schemas.track import (
    TrackPlaybackVariantBrief,
    TrackResponse,
)
from app.services.playback_variant_service import PlaybackVariantService


async def dedupe_and_build_track_list(
    session: AsyncSession,
    tracks: list[Track],
) -> list[TrackResponse]:
    pvs = PlaybackVariantService(session)
    deduped = await pvs.dedupe_track_rows_for_display(tracks)
    return await build_track_responses(session, deduped)


async def build_track_response(
    session: AsyncSession,
    track: Track,
) -> TrackResponse:
    base = TrackResponse.model_validate(track)
    pvs = PlaybackVariantService(session)
    ids = await pvs.resolve_variant_track_ids(track)
    if len(ids) <= 1:
        return base
    rows = await TrackRepository(session).get_by_ids_preserve_order(ids)
    active = [r for r in rows if r.is_active and r.is_public]
    if len(active) <= 1:
        return base
    primary = pvs.pick_primary_track(active)
    briefs: list[TrackPlaybackVariantBrief] = []
    for r in sorted(
        active,
        key=lambda x: (
            x.catalog_type,
            (x.source_platform or ""),
            x.id,
        ),
    ):
        briefs.append(
            TrackPlaybackVariantBrief(
                track_id=r.id,
                source=r.source,
                catalog_type=r.catalog_type,
                source_platform=r.source_platform,
                source_name=r.source_name,
                is_primary_for_display=r.id == primary.id,
            )
        )
    return base.model_copy(update={"playback_variants": briefs})


async def build_track_responses(
    session: AsyncSession,
    tracks: list[Track],
) -> list[TrackResponse]:
    if not tracks:
        return []
    results = await asyncio.gather(
        *[build_track_response(session, t) for t in tracks],
    )
    return list(results)


def merge_recent_listen_meta_into_responses(
    items: list[TrackResponse],
    meta_by_track_id: dict[int, tuple[datetime, int]],
) -> list[TrackResponse]:
    if not meta_by_track_id:
        return items
    out: list[TrackResponse] = []
    for item in items:
        candidate_ids = {item.id}
        for variant in item.playback_variants:
            candidate_ids.add(variant.track_id)
        best: tuple[datetime, int] | None = None
        for tid in candidate_ids:
            row = meta_by_track_id.get(tid)
            if row is None:
                continue
            if best is None or row[0] > best[0]:
                best = row
        if best is None:
            out.append(item)
            continue
        out.append(
            item.model_copy(
                update={
                    "last_listen_at": best[0],
                    "last_listen_seconds": max(0, int(best[1])),
                }
            )
        )
    return out
