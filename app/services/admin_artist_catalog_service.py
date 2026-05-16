from __future__ import annotations

from datetime import UTC, datetime

import structlog
from dotsound_private_core.services.catalog_sync_policy import (
    catalog_sync_enqueue_cooldown_remaining_seconds,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.schemas.admin_artist_catalog import (
    AdminArtistCatalogOverviewResponse,
    AdminArtistSoundcloudPatch,
    AdminCatalogReleaseCreate,
    AdminCatalogReleasePatch,
    AdminCatalogReleaseSummaryResponse,
    AdminImportByScUrlResponse,
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
        try:
            snap = await acsp.get_snapshot(artist_id)
        except Exception as exc:
            logger.warning(
                "admin_catalog_sync_snapshot_unavailable",
                artist_id=artist_id,
                error=str(exc),
            )
            snap = None
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
            image_key=artist.image_key,
            soundcloud_user_id=artist.soundcloud_user_id,
            soundcloud_permalink=artist.soundcloud_permalink,
            catalog_sync_enabled=artist.catalog_sync_enabled,
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
        sc = SoundCloudService(settings.sc_client_id, self._session)
        await sc.sync_artist_soundcloud_uploader_profile(
            artist_id,
            None,
            uploader_id=None,
        )
        out = await self.overview(artist_id)
        assert out is not None
        return out

    async def upload_artist_avatar(
        self,
        artist_id: int,
        *,
        data: bytes,
        admin_user_id: int,
    ) -> AdminArtistCatalogOverviewResponse | None:
        from app.services.file_validator import validate_image

        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            return None
        validate_image(data, filename=None)
        img_key, _, _, _ = await s3.upload_image(
            data=data,
            prefix="artists",
            max_size=settings.image_avatar_max_size,
            user_id=admin_user_id,
        )
        old_key = artist.image_key
        artist.image_key = img_key
        await self._session.commit()
        if old_key and old_key != img_key:
            try:
                await s3.delete_object(old_key)
            except Exception:
                logger.exception(
                    "admin_artist_avatar_old_delete_failed",
                    artist_id=artist_id,
                    old_key=old_key,
                )
        try:
            from app.services.search_index_notify import (
                schedule_reindex_artist,
            )

            await schedule_reindex_artist(artist_id)
        except Exception:
            logger.warning(
                "admin_artist_avatar_reindex_failed",
                artist_id=artist_id,
            )
        return await self.overview(artist_id)

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

    async def upload_release_cover(
        self,
        artist_id: int,
        release_id: int,
        *,
        data: bytes,
        content_type: str,
        admin_user_id: int,
    ) -> AdminCatalogReleaseSummaryResponse | None:
        rel = await self._catalog.get_release_for_artist(
            artist_id,
            release_id,
        )
        if rel is None:
            return None
        old_key = rel.cover_key
        img_key = await s3.upload_cover(
            data,
            content_type,
            user_id=admin_user_id,
            session=self._session,
        )
        rel.cover_key = img_key
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(rel)
        if old_key and old_key != img_key:
            try:
                await s3.delete_object(old_key)
            except Exception:
                logger.exception(
                    "admin_catalog_release_cover_old_delete_failed",
                    artist_id=artist_id,
                    release_id=release_id,
                    old_key=old_key,
                )
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

    async def enqueue_full_sync(self, artist_id: int) -> str | None:
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
        from app.services.background_jobs import IdempotencySkipped, enqueue

        try:
            await acsp.set_running(
                artist_id,
                mode="full",
                soundcloud_album_id=None,
                detail={"phase": "queued"},
            )
        except Exception as exc:
            logger.warning(
                "admin_catalog_sync_progress_unavailable",
                artist_id=artist_id,
                error=str(exc),
            )
        job_id: str | None = None
        try:
            job_id = await enqueue(
                sync_artist_catalog_task,
                payload={"artist_id": artist_id},
                idempotency_key=f"artist-catalog-sync:{artist_id}",
            )
        except IdempotencySkipped:
            logger.info(
                "admin_catalog_full_sync_already_queued",
                artist_id=artist_id,
            )
        logger.info(
            "admin_catalog_full_sync_queued",
            artist_id=artist_id,
            job_id=job_id,
        )
        return job_id

    async def enqueue_lyrics_sync(
        self,
        artist_id: int,
        *,
        with_sync: bool,
        include_existing_text: bool,
    ) -> str | None:
        artist = await self._artists.get_by_id(artist_id)
        if artist is None:
            msg = "artist not found"
            raise ValueError(msg)
        from app.services.artist_lyrics_worker import (
            enqueue_artist_lyrics_task,
        )
        from app.services.background_jobs import IdempotencySkipped, enqueue

        job_id: str | None = None
        try:
            job_id = await enqueue(
                enqueue_artist_lyrics_task,
                payload={
                    "artist_id": artist_id,
                    "with_sync": with_sync,
                    "include_existing_text": include_existing_text,
                },
                idempotency_key=(
                    "artist-lyrics-sync:"
                    f"{artist_id}:{int(with_sync)}:"
                    f"{int(include_existing_text)}"
                ),
                idempotency_ttl_seconds=300,
            )
        except IdempotencySkipped:
            logger.info(
                "admin_artist_lyrics_sync_already_queued",
                artist_id=artist_id,
            )
        logger.info(
            "admin_artist_lyrics_sync_queued",
            artist_id=artist_id,
            job_id=job_id,
            with_sync=with_sync,
            include_existing_text=include_existing_text,
        )
        return job_id

    async def enqueue_release_sync(
        self,
        artist_id: int,
        release_id: int,
    ) -> tuple[int, str | None]:
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
        from app.services.background_jobs import IdempotencySkipped, enqueue

        try:
            await acsp.set_running(
                artist_id,
                mode="release",
                soundcloud_album_id=sc_album,
                detail={
                    "phase": "queued",
                    "soundcloud_album_id": sc_album,
                },
            )
        except Exception as exc:
            logger.warning(
                "admin_catalog_sync_progress_unavailable",
                artist_id=artist_id,
                soundcloud_album_id=sc_album,
                error=str(exc),
            )
        job_id: str | None = None
        try:
            job_id = await enqueue(
                sync_artist_catalog_release_task,
                payload={
                    "artist_id": artist_id,
                    "soundcloud_album_id": sc_album,
                },
                idempotency_key=(
                    "artist-catalog-release-sync:" f"{artist_id}:{sc_album}"
                ),
            )
        except IdempotencySkipped:
            logger.info(
                "admin_catalog_release_sync_already_queued",
                artist_id=artist_id,
                release_id=release_id,
                soundcloud_album_id=sc_album,
            )
        logger.info(
            "admin_catalog_release_sync_queued",
            artist_id=artist_id,
            release_id=release_id,
            soundcloud_album_id=sc_album,
            job_id=job_id,
        )
        return sc_album, job_id

    async def import_by_sc_url(
        self,
        url_or_permalink: str,
    ) -> AdminImportByScUrlResponse:
        sc = SoundCloudService(settings.sc_client_id, self._session)
        result = await sc._resolve_profile_permalink_to_user(
            url_or_permalink.strip()
        )
        if result is None:
            raise ValueError("soundcloud_user_not_found")
        sc_user_id, sc_permalink = result

        existing = await self._artists.find_by_soundcloud_user_id(
            sc_user_id
        )
        if existing is not None:
            if not existing.catalog_sync_enabled:
                await self._artists.set_catalog_sync_enabled(
                    existing.id, enabled=True
                )
                await self._session.commit()
                await self._session.refresh(existing)
            job_id = await self._enqueue_full_sync_for_artist(existing.id)
            return AdminImportByScUrlResponse(
                artist_id=existing.id,
                artist_name=existing.name,
                created=False,
                catalog_sync_enabled=existing.catalog_sync_enabled,
                queued=True,
                job_id=job_id,
            )

        sc_user_data = await sc.fetch_soundcloud_user_by_id(sc_user_id)
        display_name: str = sc_permalink
        if sc_user_data and isinstance(
            sc_user_data.get("username"), str
        ):
            display_name = sc_user_data["username"]
        elif sc_user_data and isinstance(
            sc_user_data.get("full_name"), str
        ):
            display_name = sc_user_data["full_name"]

        from dotsound_private_core.services.artist_normalizer import (
            normalize_name,
        )

        normalized = normalize_name(display_name) or sc_permalink
        name_exists = await self._artists.find_by_normalized_name(normalized)
        if name_exists is not None:
            await self._artists.update_soundcloud_identity(
                name_exists.id,
                soundcloud_user_id=sc_user_id,
                soundcloud_permalink=sc_permalink,
            )
            await self._artists.set_catalog_sync_enabled(
                name_exists.id, enabled=True
            )
            await self._session.commit()
            job_id = await self._enqueue_full_sync_for_artist(name_exists.id)
            return AdminImportByScUrlResponse(
                artist_id=name_exists.id,
                artist_name=name_exists.name,
                created=False,
                catalog_sync_enabled=True,
                queued=True,
                job_id=job_id,
            )

        artist = await self._artists.create(
            name=display_name,
            name_normalized=normalized,
            source="soundcloud",
            external_id=str(sc_user_id),
            catalog_sync_enabled=True,
            soundcloud_user_id=sc_user_id,
            soundcloud_permalink=sc_permalink,
        )
        await self._session.commit()

        try:
            from app.services.search_index_notify import (
                schedule_reindex_artist,
            )
            await schedule_reindex_artist(artist.id)
        except Exception:
            pass

        job_id = await self._enqueue_full_sync_for_artist(artist.id)
        return AdminImportByScUrlResponse(
            artist_id=artist.id,
            artist_name=artist.name,
            created=True,
            catalog_sync_enabled=True,
            queued=True,
            job_id=job_id,
        )

    async def _enqueue_full_sync_for_artist(
        self, artist_id: int
    ) -> str | None:
        from app.services import artist_catalog_sync_progress as acsp
        from app.services.artist_catalog_sync_worker import (
            sync_artist_catalog_task,
        )
        from app.services.background_jobs import IdempotencySkipped, enqueue

        try:
            await acsp.set_running(
                artist_id,
                mode="full",
                soundcloud_album_id=None,
                detail={"phase": "queued", "source": "admin_import"},
            )
        except Exception:
            pass
        try:
            return await enqueue(
                sync_artist_catalog_task,
                payload={"artist_id": artist_id},
                idempotency_key=f"artist-catalog-sync:{artist_id}",
            )
        except IdempotencySkipped:
            logger.info(
                "admin_import_sc_catalog_sync_already_queued",
                artist_id=artist_id,
            )
            return None
