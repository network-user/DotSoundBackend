from __future__ import annotations

from datetime import UTC, datetime

import structlog
from dotsound_private_core.services.catalog_sync_policy import (
    catalog_sync_enqueue_cooldown_remaining_seconds,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.schemas.admin_artist_catalog import (
    AdminArtistCatalogOverviewResponse,
    AdminArtistSoundcloudPatch,
    AdminCatalogReleaseCreate,
    AdminCatalogReleasePatch,
    AdminCatalogReleaseSummaryResponse,
)
from app.schemas.artist_catalog import ArtistCatalogReleaseDetailResponse
from app.services import artist_catalog_sync_progress as acsp
from app.services.admin_service import AdminService
from app.services.artist_catalog_read_service import (
    ArtistCatalogReadService,
)
from app.services.soundcloud_service import SoundCloudService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AdminArtistCatalogService:
    COOLDOWN_ENQUEUE_DETAIL = "catalog sync cooldown"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._artists = ArtistRepository(session)
        self._catalog = ArtistCatalogRepository(session)
        self._read = ArtistCatalogReadService(session)
        self._admin = AdminService(session)

    async def artist_exists(self, artist_id: int) -> bool:
        return await self._artists.get_by_id(artist_id) is not None

    async def _autofill_soundcloud_user_id_if_missing(
        self,
        artist_id: int,
    ) -> None:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None or artist.soundcloud_user_id is not None:
            return
        sc = SoundCloudService(settings.sc_client_id, self._session)
        await sc.try_autofill_soundcloud_user_id_for_artist(artist_id)

    async def _ensure_catalog_sync_enqueue_allowed(
        self,
        artist_id: int,
    ) -> None:
        last = await self._catalog.latest_synced_at_for_artist(artist_id)
        rem = catalog_sync_enqueue_cooldown_remaining_seconds(
            last,
            datetime.now(UTC),
        )
        if rem > 0:
            raise ValueError(self.COOLDOWN_ENQUEUE_DETAIL)

    async def overview(
        self,
        artist_id: int,
    ) -> AdminArtistCatalogOverviewResponse | None:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            return None
        rows = await self._catalog.list_releases_with_track_counts(
            artist_id,
        )
        items = [
            AdminCatalogReleaseSummaryResponse(
                id=rel.id,
                title=rel.title,
                release_kind=rel.release_kind,
                released_at=rel.released_at,
                display_position=rel.display_position,
                track_count=n,
                cover_key=rel.cover_key,
                manual_lock=rel.manual_lock,
                soundcloud_album_id=rel.soundcloud_album_id,
            )
            for rel, n in rows
        ]
        snap = await acsp.get_snapshot(artist_id)
        cs_state = "idle"
        cs_mode = None
        cs_album = None
        cs_err = None
        cs_detail = None
        cs_upd = None
        if snap:
            raw_st = snap.get("state")
            if raw_st in ("running", "success", "error"):
                cs_state = raw_st
            raw_md = snap.get("mode")
            if raw_md in ("full", "release"):
                cs_mode = raw_md
            aid = snap.get("soundcloud_album_id")
            if isinstance(aid, int):
                cs_album = aid
            err = snap.get("error")
            if isinstance(err, str):
                cs_err = err
            det = snap.get("detail")
            if isinstance(det, dict):
                cs_detail = det
            upd = snap.get("updated_at")
            if isinstance(upd, str):
                cs_upd = upd
        return AdminArtistCatalogOverviewResponse(
            artist_id=artist.id,
            soundcloud_user_id=artist.soundcloud_user_id,
            soundcloud_permalink=artist.soundcloud_permalink,
            releases=items,
            releases_total=len(items),
            catalog_sync_state=cs_state,
            catalog_sync_mode=cs_mode,
            catalog_sync_soundcloud_album_id=cs_album,
            catalog_sync_error=cs_err,
            catalog_sync_detail=cs_detail,
            catalog_sync_updated_at=cs_upd,
        )

    async def release_detail(
        self,
        artist_id: int,
        release_id: int,
    ) -> ArtistCatalogReleaseDetailResponse | None:
        return await self._read.get_release_detail(
            artist_id,
            release_id,
        )

    async def patch_soundcloud(
        self,
        artist_id: int,
        body: AdminArtistSoundcloudPatch,
    ) -> AdminArtistCatalogOverviewResponse | None:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            return None
        patch = body.model_dump(exclude_unset=True)
        if not patch:
            return await self.overview(artist_id)
        uid = artist.soundcloud_user_id
        if "soundcloud_user_id" in patch:
            uid = patch["soundcloud_user_id"]
        if uid is not None:
            other = await self._artists.find_by_soundcloud_user_id(
                int(uid),
                exclude_artist_id=artist_id,
            )
            if other is not None:
                msg = "soundcloud_user_id already linked to another artist"
                raise ValueError(msg)
        pl = artist.soundcloud_permalink
        if "soundcloud_permalink" in patch:
            raw = patch["soundcloud_permalink"]
            if raw is None:
                pl = None
            else:
                s = str(raw).strip()
                pl = s or None
        await self._artists.update_soundcloud_identity(
            artist_id,
            soundcloud_user_id=uid,
            soundcloud_permalink=pl,
        )
        await self._session.commit()
        out = await self.overview(artist_id)
        assert out is not None
        return out

    async def create_release(
        self,
        artist_id: int,
        body: AdminCatalogReleaseCreate,
    ) -> AdminCatalogReleaseSummaryResponse | None:
        if not await self._artists.get_by_id(artist_id):
            return None
        rel = await self._catalog.create_manual_release(
            artist_id,
            title=body.title,
            release_kind=body.release_kind,
            released_at=body.released_at,
            soundcloud_album_id=body.soundcloud_album_id,
            manual_lock=body.manual_lock,
            cover_key=None,
        )
        await self._session.commit()
        return AdminCatalogReleaseSummaryResponse(
            id=rel.id,
            title=rel.title,
            release_kind=rel.release_kind,
            released_at=rel.released_at,
            display_position=rel.display_position,
            track_count=0,
            cover_key=rel.cover_key,
            manual_lock=rel.manual_lock,
            soundcloud_album_id=rel.soundcloud_album_id,
        )

    async def patch_release(
        self,
        artist_id: int,
        release_id: int,
        body: AdminCatalogReleasePatch,
    ) -> AdminCatalogReleaseSummaryResponse | None:
        rel = await self._catalog.get_release_for_artist(
            artist_id,
            release_id,
        )
        if rel is None:
            return None
        patch = body.model_dump(exclude_unset=True)
        if "title" in patch and patch["title"] is not None:
            rel.title = str(patch["title"])[:512]
        if "release_kind" in patch:
            rk = patch["release_kind"]
            if rk is None or rk == "":
                rel.release_kind = None
            else:
                rel.release_kind = str(rk).strip()[:32]
        if "released_at" in patch:
            rel.released_at = patch["released_at"]
        if "display_position" in patch:
            rel.display_position = int(patch["display_position"])
        if "manual_lock" in patch:
            rel.manual_lock = bool(patch["manual_lock"])
        await self._session.flush()
        await self._session.commit()
        ordered = await self._catalog.get_release_tracks_ordered(
            release_id,
        )
        cnt = len(ordered)
        return AdminCatalogReleaseSummaryResponse(
            id=rel.id,
            title=rel.title,
            release_kind=rel.release_kind,
            released_at=rel.released_at,
            display_position=rel.display_position,
            track_count=cnt,
            cover_key=rel.cover_key,
            manual_lock=rel.manual_lock,
            soundcloud_album_id=rel.soundcloud_album_id,
        )

    async def delete_release(
        self,
        artist_id: int,
        release_id: int,
    ) -> bool:
        ok = await self._catalog.delete_release_for_artist(
            artist_id,
            release_id,
        )
        if ok:
            await self._session.commit()
        return ok

    async def reorder_releases(
        self,
        artist_id: int,
        ordered_release_ids: list[int],
    ) -> None:
        if not await self._artists.get_by_id(artist_id):
            msg = "artist not found"
            raise ValueError(msg)
        await self._catalog.apply_release_display_order(
            artist_id,
            ordered_release_ids,
        )
        await self._session.commit()

    async def set_release_tracks(
        self,
        artist_id: int,
        release_id: int,
        track_ids: list[int],
    ) -> ArtistCatalogReleaseDetailResponse | None:
        rel = await self._catalog.get_release_for_artist(
            artist_id,
            release_id,
        )
        if rel is None:
            return None
        seen: set[int] = set()
        for tid in track_ids:
            if tid in seen:
                msg = "duplicate track_id"
                raise ValueError(msg)
            seen.add(tid)
        for pos, tid in enumerate(track_ids):
            tr = await self._admin.get_track(tid)
            if tr is None:
                msg = "unknown track_id"
                raise ValueError(msg)
            await self._artists.link_track(
                tid,
                artist_id,
                position=pos,
            )
        await self._catalog.replace_release_tracks(rel.id, track_ids)
        await self._session.commit()
        return await self._read.get_release_detail(artist_id, release_id)

    async def enqueue_full_sync(self, artist_id: int) -> None:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            msg = "artist not found"
            raise ValueError(msg)
        await self._autofill_soundcloud_user_id_if_missing(artist_id)
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            msg = "artist not found"
            raise ValueError(msg)
        if artist.soundcloud_user_id is None:
            msg = "artist has no soundcloud_user_id"
            raise ValueError(msg)
        await self._ensure_catalog_sync_enqueue_allowed(artist_id)
        from app.services.artist_catalog_sync_worker import (
            sync_artist_catalog_task,
        )

        await sync_artist_catalog_task.kiq(artist_id=artist_id)
        await acsp.set_running(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
        )
        logger.info(
            "admin_catalog_full_sync_queued",
            artist_id=artist_id,
        )

    async def enqueue_release_sync(
        self,
        artist_id: int,
        release_id: int,
    ) -> int:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            msg = "artist not found"
            raise ValueError(msg)
        await self._autofill_soundcloud_user_id_if_missing(artist_id)
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            msg = "artist not found"
            raise ValueError(msg)
        if artist.soundcloud_user_id is None:
            msg = "artist has no soundcloud_user_id"
            raise ValueError(msg)
        rel = await self._catalog.get_release_for_artist(
            artist_id,
            release_id,
        )
        if rel is None:
            msg = "release not found"
            raise ValueError(msg)
        if rel.soundcloud_album_id is None:
            msg = "release has no soundcloud_album_id"
            raise ValueError(msg)
        await self._ensure_catalog_sync_enqueue_allowed(artist_id)
        sc_album = int(rel.soundcloud_album_id)
        from app.services.artist_catalog_sync_worker import (
            sync_artist_catalog_release_task,
        )

        await sync_artist_catalog_release_task.kiq(
            artist_id=artist_id,
            soundcloud_album_id=sc_album,
        )
        await acsp.set_running(
            artist_id,
            mode="release",
            soundcloud_album_id=sc_album,
        )
        logger.info(
            "admin_catalog_release_sync_queued",
            artist_id=artist_id,
            release_id=release_id,
            soundcloud_album_id=sc_album,
        )
        return sc_album
