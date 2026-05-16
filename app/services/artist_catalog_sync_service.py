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
from app.models.artist import Artist
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.services import artist_catalog_sync_progress as acsp
from app.services.artist_service import ArtistService
from app.services.soundcloud_service import (
    SoundCloudService,
    SoundCloudStationNotAvailable,
    synthetic_soundcloud_id_for_artist_station,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND = "dotsound_sc_artist_station"


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

    async def _load_artist_with_autofill_sc_user(
        self,
        artist_id: int,
    ) -> tuple[Artist, SoundCloudService]:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        sc = SoundCloudService(settings.sc_client_id, self._session)
        if artist.soundcloud_user_id is None:
            await sc.try_autofill_soundcloud_user_id_for_artist(artist_id)
            artist = await self._artists.get_by_id(artist_id)
            if artist is None:
                raise ValueError("artist not found")
        if artist.soundcloud_user_id is None:
            raise ValueError("artist has no soundcloud_user_id")
        return artist, sc

    @staticmethod
    def _soundcloud_user_id_int(artist: Artist) -> int:
        raw = artist.soundcloud_user_id
        if raw is None:
            msg = "artist has no soundcloud_user_id"
            raise ValueError(msg)
        return int(raw)

    async def sync_full_artist(
        self,
        artist_id: int,
        *,
        skip_background_lyrics: bool = False,
    ) -> dict[str, Any]:
        artist, sc = await self._load_artist_with_autofill_sc_user(artist_id)
        await sc.sync_artist_soundcloud_uploader_profile(
            artist_id,
            None,
            uploader_id=None,
        )
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        sc_uid = self._soundcloud_user_id_int(artist)
        await sc.ensure_soundcloud_ids_for_artist(
            artist_id,
            sc_uid,
            artist.soundcloud_permalink,
        )
        await acsp.merge_running_detail(
            artist_id,
            {"phase": "list_soundcloud_albums"},
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
        await acsp.merge_running_detail(
            artist_id,
            {
                "phase": "albums",
                "albums_total": len(albums),
                "albums_done": 0,
            },
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
            await acsp.merge_running_detail(
                artist_id,
                {
                    "phase": "albums",
                    "albums_total": len(albums),
                    "albums_done": stats["albums_synced"],
                },
            )
        st: dict[str, bool] = {
            "synced": False,
            "skipped_manual": False,
        }
        await acsp.merge_running_detail(
            artist_id,
            {"phase": "station_similar"},
        )
        try:
            st = await self._sync_artist_similar_station_core(
                artist_id,
                artist,
                sc,
                sc_uid,
                skip_background_lyrics=skip_background_lyrics,
            )
            await self._session.commit()
        except SoundCloudStationNotAvailable as exc:
            logger.info(
                "catalog_sync_station_not_available",
                artist_id=artist_id,
                reason=exc.reason,
            )
            await self._session.rollback()
        except Exception as exc:
            logger.warning(
                "catalog_sync_station_failed",
                artist_id=artist_id,
                error=str(exc),
                exc_info=True,
            )
            await self._session.rollback()
            await self._enqueue_station_retry(artist_id)
        stats["station_synced"] = st.get("synced", False)
        stats["station_skipped_manual"] = st.get(
            "skipped_manual",
            False,
        )
        logger.info(
            "catalog_sync_full_done",
            artist_id=artist_id,
            **stats,
        )
        return stats

    async def sync_artist_similar_station(
        self,
        artist_id: int,
        *,
        skip_background_lyrics: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        artist, sc = await self._load_artist_with_autofill_sc_user(artist_id)
        await sc.sync_artist_soundcloud_uploader_profile(
            artist_id,
            None,
            uploader_id=None,
        )
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        sc_uid = self._soundcloud_user_id_int(artist)
        await sc.ensure_soundcloud_ids_for_artist(
            artist_id,
            sc_uid,
            artist.soundcloud_permalink,
        )
        try:
            core = await self._sync_artist_similar_station_core(
                artist_id,
                artist,
                sc,
                sc_uid,
                skip_background_lyrics=skip_background_lyrics,
                force=force,
            )
        except SoundCloudStationNotAvailable as exc:
            logger.info(
                "catalog_sync_station_not_available",
                artist_id=artist_id,
                reason=exc.reason,
            )
            await self._session.rollback()
            return {"status": "skipped", "reason": f"no_station:{exc.reason}"}
        except Exception as exc:
            logger.warning(
                "catalog_sync_station_failed",
                artist_id=artist_id,
                error=str(exc),
                exc_info=True,
            )
            await self._session.rollback()
            return {"status": "error", "detail": str(exc)}
        if core.get("skipped_manual"):
            await self._session.commit()
            return {"status": "skipped", "reason": "manual_lock"}
        await self._session.commit()
        logger.info(
            "catalog_sync_station_done",
            artist_id=artist_id,
            forced=force,
        )
        return {"status": "ok", "forced": force}

    async def _sync_artist_similar_station_core(
        self,
        artist_id: int,
        artist: Artist,
        sc: SoundCloudService,
        sc_uid: int,
        *,
        skip_background_lyrics: bool,
        force: bool = False,
    ) -> dict[str, Any]:
        synthetic = synthetic_soundcloud_id_for_artist_station(sc_uid)
        existing = await self._catalog.get_by_artist_and_sc_album(
            artist_id,
            synthetic,
        )
        if existing is not None and existing.manual_lock and not force:
            return {"skipped_manual": True, "synced": False}
        display_position = (
            existing.display_position
            if existing is not None
            else await self._catalog.next_display_position(artist_id)
        )
        expanded = await sc.fetch_expanded_artist_station_playlist(sc_uid)
        expanded["title"] = f"Похожее: «{artist.name}»"
        await self._sync_one_album_expanded(
            sc,
            artist_id=artist_id,
            expanded=expanded,
            display_position=display_position,
            skip_background_lyrics=skip_background_lyrics,
            release_kind_override=DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND,
        )
        return {"skipped_manual": False, "synced": True}

    async def _enqueue_station_retry(self, artist_id: int) -> None:
        """Enqueue a standalone station-sync task after a transient failure.

        Only called when station sync fails with a real error (not
        SoundCloudStationNotAvailable, which is a permanent condition).
        The retry runs independently so the full catalog-sync result is
        not blocked.
        """
        try:
            from app.services.artist_catalog_sync_worker import (
                sync_artist_similar_station_task,
            )

            await sync_artist_similar_station_task.kiq(artist_id)
            logger.info(
                "catalog_sync_station_retry_enqueued",
                artist_id=artist_id,
            )
        except Exception as exc:
            logger.warning(
                "catalog_sync_station_retry_enqueue_failed",
                artist_id=artist_id,
                error=str(exc),
            )

    async def sync_single_release(
        self,
        artist_id: int,
        soundcloud_album_id: int,
        *,
        skip_background_lyrics: bool = False,
    ) -> dict[str, Any]:
        artist, sc = await self._load_artist_with_autofill_sc_user(artist_id)
        await sc.sync_artist_soundcloud_uploader_profile(
            artist_id,
            None,
            uploader_id=None,
        )
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            raise ValueError("artist not found")
        sc_uid = self._soundcloud_user_id_int(artist)
        await sc.ensure_soundcloud_ids_for_artist(
            artist_id,
            sc_uid,
            artist.soundcloud_permalink,
        )
        await acsp.merge_running_detail(
            artist_id,
            {
                "phase": "release",
                "soundcloud_album_id": soundcloud_album_id,
            },
        )
        pl = await sc.fetch_playlist_by_id(soundcloud_album_id)
        expanded = await sc.expand_playlist_stub_tracks(pl)
        user_blob = expanded.get("user")
        owner_id = user_blob.get("id") if isinstance(user_blob, dict) else None
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
        release_kind_override: str | None = None,
    ) -> None:
        raw_id = expanded.get("id")
        if raw_id is None:
            raise ValueError("album payload missing id")
        soundcloud_album_id = int(raw_id)
        title = str(expanded.get("title") or "Untitled")
        if release_kind_override is not None:
            rk = release_kind_override
        else:
            pt = expanded.get("playlist_type") or expanded.get("set_type")
            if pt is None:
                rk = None
            elif isinstance(pt, str):
                rk = pt
            else:
                rk = str(pt)
        released_at = _parse_optional_date(
            expanded.get("release_date") or expanded.get("display_date")
        )
        cover_key = await sc.download_artwork_as_cover_key(
            (
                expanded.get("artwork_url")
                if isinstance(expanded.get("artwork_url"), str)
                else None
            ),
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
        is_station = rk == DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND
        artist_svc = ArtistService(self._session) if is_station else None
        ordered_ids: list[int] = []
        lyrics_track_ids: list[int] = []
        for idx, tr in enumerate(clipped):
            if not isinstance(tr, dict):
                continue
            try:
                track = await sc.import_or_get_track(
                    tr,
                    settings.catalog_uploader_id,
                    skip_background_lyrics=skip_background_lyrics,
                )
            except Exception as _track_exc:
                from fastapi import HTTPException as _HTTPException

                _skip_codes = {
                    "soundcloud_track_unverified",
                    "soundcloud_track_not_importable",
                }
                _detail = (
                    _track_exc.detail
                    if isinstance(_track_exc, _HTTPException)
                    else {}
                )
                _code = (
                    _detail.get("code", "")
                    if isinstance(_detail, dict)
                    else ""
                )
                if _code in _skip_codes:
                    logger.info(
                        "catalog_sync_track_policy_skip",
                        sc_url=tr.get("permalink_url"),
                        soundcloud_album_id=soundcloud_album_id,
                        code=_code,
                        reason=_detail.get("reason"),
                    )
                    continue
                logger.warning(
                    "catalog_sync_track_import_error",
                    sc_url=tr.get("permalink_url"),
                    soundcloud_album_id=soundcloud_album_id,
                    error=repr(_track_exc)[:300],
                )
                continue
            if is_station:
                # Station tracks belong to *other* (similar) artists,
                # not to the seed artist whose page hosts the station.
                # Linking them to seed_artist_id would poison
                # `GET /artists/{seed}/tracks` with foreign tracks.
                # Instead, resolve and link the track's real artist
                # string so the proper artist page picks them up.
                if track.artist and artist_svc is not None:
                    try:
                        await artist_svc.resolve_and_link(
                            track_id=track.id,
                            raw_artist_string=track.artist,
                            source="soundcloud",
                            skip_catalog_sync=True,
                        )
                    except Exception as exc:
                        logger.warning(
                            "station_track_real_artist_link_failed",
                            artist_id=artist_id,
                            track_id=track.id,
                            error=str(exc),
                        )
            else:
                await self._artists.link_track(
                    track.id,
                    artist_id,
                    position=idx,
                )
            ordered_ids.append(track.id)
            if not skip_background_lyrics:
                lyrics_track_ids.append(track.id)
        await self._catalog.replace_release_tracks(rel.id, ordered_ids)
        for track_id in lyrics_track_ids:
            await self._enqueue_track_lyrics(track_id)

    async def _enqueue_track_lyrics(self, track_id: int) -> None:
        try:
            if settings.lyrics_global_orchestrator_enabled:
                from app.services import lyrics_global_orchestrator

                await lyrics_global_orchestrator.enqueue(
                    track_id,
                    with_sync=True,
                    force_sync_existing_text=True,
                )
                return
            from app.services.lyrics_service import LyricsService

            await LyricsService(self._session).enqueue_background_lyrics(
                track_id,
                requested_by_user_id=None,
                with_sync=True,
                bypass_cache=False,
                force_sync_existing_text=True,
            )
        except Exception as exc:
            logger.warning(
                "catalog_sync_lyrics_enqueue_failed",
                track_id=track_id,
                error=str(exc),
            )
