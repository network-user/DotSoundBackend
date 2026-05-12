from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import quote

from dotsound_private_core.services.playback_variant_policy import (
    catalog_rank,
    external_platform_rank,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.album import AlbumRepository
from app.repositories.artist import ArtistRepository
from app.repositories.lyrics import LyricsRepository
from app.repositories.signal import ListenEventRepository
from app.repositories.track import TrackRepository
from app.schemas.track import (
    TrackArtistBrief,
    TrackPlaybackVariantBrief,
    TrackResponse,
)
from app.services.playback_variant_service import PlaybackVariantService


def _pick_display_cover_key(rows: list[Track]) -> str | None:
    with_cover = [r for r in rows if r.cover_key]
    if not with_cover:
        return None
    chosen = sorted(
        with_cover,
        key=lambda t: (
            catalog_rank(t.catalog_type),
            external_platform_rank(t.source_platform),
            -(t.play_count or 0),
            t.id,
        ),
    )[0]
    return chosen.cover_key


def _artist_briefs(
    rows: list[tuple],
) -> list[TrackArtistBrief]:
    return [
        TrackArtistBrief(
            id=artist.id,
            name=artist.name,
            role=role,
            image_url=(
                "/api/v1/tracks/cover_proxy"
                f"?key={quote(artist.image_key, safe='')}"
                if artist.image_key
                else None
            ),
        )
        for artist, role, _ in rows
    ]


async def _apply_resume_position(
    session: AsyncSession,
    resp: TrackResponse,
    viewer_id: int,
) -> TrackResponse:
    positions = await ListenEventRepository(session).latest_resume_position(
        viewer_id, [int(resp.id)]
    )
    pos = positions.get(int(resp.id))
    if not pos:
        return resp
    return resp.model_copy(update={"resume_position_seconds": pos})


async def dedupe_and_build_track_list(
    session: AsyncSession,
    tracks: list[Track],
    *,
    viewer_id: int | None = None,
) -> list[TrackResponse]:
    pvs = PlaybackVariantService(session)
    deduped = await pvs.dedupe_track_rows_for_display(tracks)
    return await build_track_responses(session, deduped, viewer_id=viewer_id)


async def build_track_response(
    session: AsyncSession,
    track: Track,
    *,
    include_has_lyrics: bool = True,
    preloaded_artists: list[tuple] | None = None,
    viewer_id: int | None = None,
) -> TrackResponse:
    base = TrackResponse.model_validate(track)
    pvs = PlaybackVariantService(session)
    ids = await pvs.resolve_variant_track_ids(track)
    variant_rows: list[Track] | None = None
    if len(ids) > 1:
        variant_rows = await TrackRepository(
            session
        ).get_by_ids_preserve_order(
            ids,
        )
    active: list[Track] = []
    if variant_rows is not None:
        active = [r for r in variant_rows if r.is_active and r.is_public]

    enriched: TrackResponse
    if not active or len(active) <= 1:
        enriched = base
    else:
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
                    is_primary_for_display=(r.id == primary.id),
                )
            )
        enriched = base.model_copy(
            update={"playback_variants": briefs},
        )

    if not enriched.cover_key and active:
        borrowed = _pick_display_cover_key(active)
        if borrowed:
            enriched = enriched.model_copy(update={"cover_key": borrowed})
    if not enriched.cover_key and track.album_id is not None:
        album = await AlbumRepository(session).get_by_id(
            int(track.album_id),
        )
        if album and album.cover_key:
            enriched = enriched.model_copy(
                update={"cover_key": album.cover_key},
            )

    if preloaded_artists is not None:
        artist_rows = preloaded_artists
    else:
        artist_rows = await ArtistRepository(
            session
        ).get_track_artists_with_roles(int(enriched.id))
    enriched = enriched.model_copy(
        update={"track_artists": _artist_briefs(artist_rows)}
    )

    if not include_has_lyrics:
        if viewer_id is not None:
            enriched = await _apply_resume_position(
                session, enriched, viewer_id
            )
        return enriched
    has_l = await LyricsRepository(
        session,
    ).has_nonempty_plain_text(int(enriched.id))
    result = enriched.model_copy(update={"has_lyrics": has_l})
    if viewer_id is not None:
        result = await _apply_resume_position(session, result, viewer_id)
    return result


async def build_track_responses(
    session: AsyncSession,
    tracks: list[Track],
    *,
    viewer_id: int | None = None,
) -> list[TrackResponse]:
    if not tracks:
        return []

    track_ids = [t.id for t in tracks]
    artists_by_track = await ArtistRepository(
        session
    ).get_tracks_artists_with_roles_batch(track_ids)

    results = await asyncio.gather(
        *[
            build_track_response(
                session,
                t,
                include_has_lyrics=False,
                preloaded_artists=artists_by_track.get(t.id, []),
            )
            for t in tracks
        ],
    )
    lyr = LyricsRepository(session)
    present = await lyr.nonempty_plain_track_ids([int(r.id) for r in results])
    final: list[TrackResponse] = [
        r.model_copy(update={"has_lyrics": (int(r.id) in present)})
        for r in results
    ]

    if viewer_id is not None and final:
        resp_ids = [int(r.id) for r in final]
        positions = await ListenEventRepository(
            session
        ).latest_resume_position(viewer_id, resp_ids)
        if positions:
            final = [
                r.model_copy(
                    update={"resume_position_seconds": positions[int(r.id)]}
                )
                if positions.get(int(r.id))
                else r
                for r in final
            ]

    return final


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
