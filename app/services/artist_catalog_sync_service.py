from __future__ import annotations

from datetime import date, datetime
from typing import Any

import structlog
from dotsound_private_core.services.catalog_sync_policy import (
    CATALOG_SYNC_ALBUMS_PAGE_SIZE,
    CATALOG_SYNC_MAX_RELEASES_PER_FULL_RUN,
    CATALOG_SYNC_MAX_TRACKS_PER_RELEASE,
    clip_albums_for_full_sync,
    clip_tracks_for_release_sync,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.services.soundcloud_service import SoundCloudService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _parse_optional_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    head = s[:10]
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


class ArtistCatalogSyncService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._artists = ArtistRepository(session)
        self._catalog = ArtistCatalogRepository(session)

    async def sync_full_artist(
        self,
        artist_id: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> dict[str, Any]:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        if artist.soundcloud_user_id is None:
            raise ValueError("artist has no soundcloud_user_id")
        sc_uid = int(artist.soundcloud_user_id)
        sc = SoundCloudService(settings.sc_client_id, self._session)
        await sc.ensure_soundcloud_ids_for_artist(
            artist_id,
            sc_uid,
            artist.soundcloud_permalink,
        )
        raw_albums, source_truncated = await sc.list_user_albums(
            sc_uid,
            limit_per_page=CATALOG_SYNC_ALBUMS_PAGE_SIZE,
            max_total=CATALOG_SYNC_MAX_RELEASES_PER_FULL_RUN,
        )
        albums = clip_albums_for_full_sync(
            raw_albums,
            CATALOG_SYNC_MAX_RELEASES_PER_FULL_RUN,
        )
        stats: dict[str, Any] = {
            "albums_seen": len(albums),
            "albums_synced": 0,
            "skipped_manual": 0,
            "albums_source_truncated": source_truncated,
        }
        for pos, raw in enumerate(albums):
            if not isinstance(raw, dict):
                continue
            expanded = await sc.expand_playlist_stub_tracks(raw)
            aid = expanded.get("id")
            if aid is None:
                logger.warning(
                    "catalog_sync_album_missing_id",
                    artist_id=artist_id,
                )
                continue
            sc_album_id = int(aid)
            existing = await self._catalog.get_by_artist_and_sc_album(
                artist_id,
                sc_album_id,
            )
            if existing is not None and existing.manual_lock:
                stats["skipped_manual"] += 1
                continue
            await self._sync_one_album_expanded(
                sc,
                artist_id=artist_id,
                expanded=expanded,
                display_position=pos,
                skip_background_lyrics=skip_background_lyrics,
            )
            stats["albums_synced"] += 1
            await self._session.commit()
        logger.info(
            "catalog_sync_full_done",
            artist_id=artist_id,
            **stats,
        )
        return stats

    async def sync_single_release(
        self,
        artist_id: int,
        soundcloud_album_id: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> dict[str, Any]:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        if artist.soundcloud_user_id is None:
            raise ValueError("artist has no soundcloud_user_id")
        sc_uid = int(artist.soundcloud_user_id)
        sc = SoundCloudService(settings.sc_client_id, self._session)
        await sc.ensure_soundcloud_ids_for_artist(
            artist_id,
            sc_uid,
            artist.soundcloud_permalink,
        )
        pl = await sc.fetch_playlist_by_id(soundcloud_album_id)
        expanded = await sc.expand_playlist_stub_tracks(pl)
        user_blob = expanded.get("user")
        owner_id = (
            user_blob.get("id")
            if isinstance(user_blob, dict)
            else None
        )
        if owner_id is None or int(owner_id) != sc_uid:
            raise ValueError(
                "playlist does not belong to this artist's soundcloud_user_id"
            )
        existing = await self._catalog.get_by_artist_and_sc_album(
            artist_id,
            soundcloud_album_id,
        )
        if existing is not None and existing.manual_lock:
            await self._session.commit()
            return {"status": "skipped", "reason": "manual_lock"}
        display_position = (
            existing.display_position
            if existing is not None
            else await self._catalog.next_display_position(artist_id)
        )
        await self._sync_one_album_expanded(
            sc,
            artist_id=artist_id,
            expanded=expanded,
            display_position=display_position,
            skip_background_lyrics=skip_background_lyrics,
        )
        await self._session.commit()
        logger.info(
            "catalog_sync_single_done",
            artist_id=artist_id,
            soundcloud_album_id=soundcloud_album_id,
        )
        return {"status": "ok", "soundcloud_album_id": soundcloud_album_id}

    async def _sync_one_album_expanded(
        self,
        sc: SoundCloudService,
        *,
        artist_id: int,
        expanded: dict[str, Any],
        display_position: int,
        skip_background_lyrics: bool,
    ) -> None:
        raw_id = expanded.get("id")
        if raw_id is None:
            raise ValueError("album payload missing id")
        soundcloud_album_id = int(raw_id)
        title = str(expanded.get("title") or "Untitled")
        pt = expanded.get("playlist_type") or expanded.get("set_type")
        if pt is None:
            rk = None
        elif isinstance(pt, str):
            rk = pt
        else:
            rk = str(pt)
        released_at = _parse_optional_date(
            expanded.get("release_date")
            or expanded.get("display_date")
        )
        cover_key = await sc.download_artwork_as_cover_key(
            expanded.get("artwork_url")
            if isinstance(expanded.get("artwork_url"), str)
            else None,
            uploader_id=settings.catalog_uploader_id,
        )
        rel = await self._catalog.upsert_release(
            artist_id,
            soundcloud_album_id,
            title=title,
            release_kind=rk,
            released_at=released_at,
            cover_key=cover_key,
            display_position=display_position,
        )
        raw_tracks = expanded.get("tracks")
        tracks_list = raw_tracks if isinstance(raw_tracks, list) else []
        clipped = clip_tracks_for_release_sync(
            tracks_list,
            CATALOG_SYNC_MAX_TRACKS_PER_RELEASE,
        )
        if len(clipped) < len(tracks_list):
            logger.warning(
                "catalog_sync_tracks_capped",
                artist_id=artist_id,
                soundcloud_album_id=soundcloud_album_id,
                kept=len(clipped),
                dropped=len(tracks_list) - len(clipped),
            )
        ordered_ids: list[int] = []
        for idx, tr in enumerate(clipped):
            if not isinstance(tr, dict):
                continue
            track = await sc.import_or_get_track(
                tr,
                settings.catalog_uploader_id,
                skip_background_lyrics=skip_background_lyrics,
            )
            await self._artists.link_track(
                track.id,
                artist_id,
                position=idx,
            )
            ordered_ids.append(track.id)
        await self._catalog.replace_release_tracks(rel.id, ordered_ids)
