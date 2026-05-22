import uuid

import structlog
from dotsound_private_core import censor_text
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.models.lyrics_translation import (
    TrackLyricsTranslation,
)
from app.models.track import Track
from app.repositories.lyrics import LyricsRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.lyrics_state import has_nonempty_synced_lines

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_URGENT_REMOTE_SYNC_PRIORITY = 1_000_000


class LyricsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = LyricsRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._session = session

    async def _resolve_user_id(self, user_id: int) -> int:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user.id

    async def _get_owned_track(self, track_id: int, user_id: int) -> Track:
        return await self._get_editable_track(track_id, user_id)

    async def _get_editable_track(self, track_id: int, user_id: int) -> Track:
        """Resolve a track and verify the caller is allowed to
        edit its lyrics.

        For ``catalog_type == 'external_reference'`` (imported
        tracks like Yandex Music) edits are admin-only — the
        catalog is shared across every importer's library and
        per-user edits would create attribution chaos plus a
        legal-content-modification surface.

        For UGC and licensed catalog the original uploader keeps
        full edit rights as before.
        """
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if track.catalog_type != "ugc":
            if not user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Lyrics for non-UGC tracks can "
                        "only be edited by admins"
                    ),
                )
            return track
        if track.uploaded_by_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not the track owner",
            )
        return track

    async def get_lyrics(
        self,
        track_id: int,
        requester_id: int | None = None,
    ) -> TrackLyrics | None:
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        is_owner = (
            requester_id
            and track.uploaded_by_id == requester_id
            and track.catalog_type == "ugc"
        )
        if not track.is_public and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        return await self._repo.get_by_track_id(track_id)

    async def create_or_update(
        self, track_id: int, user_id: int, plain_text: str
    ) -> TrackLyrics:
        await self._get_owned_track(track_id, user_id)
        lyrics = await self._repo.create_or_update(track_id, plain_text)
        await self._session.commit()
        logger.info("lyrics_saved", track_id=track_id)
        return lyrics

    async def update_sync(
        self,
        track_id: int,
        user_id: int,
        synced_lines: list[dict[str, object]],
    ) -> TrackLyrics:
        await self._get_owned_track(track_id, user_id)
        lyrics = await self._repo.update_sync(track_id, synced_lines)
        if not lyrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lyrics not found — upload plain text first",
            )
        await self._session.commit()
        logger.info("lyrics_sync_updated", track_id=track_id)
        return lyrics

    async def delete_lyrics(self, track_id: int, user_id: int) -> bool:
        await self._get_owned_track(track_id, user_id)
        removed = await self._repo.delete_by_track_id(track_id)
        if removed:
            await self._session.commit()
        return removed

    async def list_translations(
        self,
        track_id: int,
        requester_id: int | None = None,
    ) -> list[TrackLyricsTranslation]:
        lyrics = await self.get_lyrics(track_id, requester_id=requester_id)
        if not lyrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lyrics not found",
            )
        return await self._repo.list_translations(lyrics.id)

    async def upsert_translation(
        self,
        track_id: int,
        user_id: int,
        language_code: str,
        translated_text: str,
    ) -> TrackLyricsTranslation:
        await self._get_owned_track(track_id, user_id)
        lyrics = await self._repo.get_by_track_id(track_id)
        if not lyrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lyrics not found — upload plain text first",
            )
        translation = await self._repo.upsert_translation(
            track_lyrics_id=lyrics.id,
            language_code=language_code,
            translated_text=censor_text(translated_text),
        )
        await self._session.commit()
        return translation

    async def delete_translation(
        self,
        track_id: int,
        user_id: int,
        language_code: str,
    ) -> bool:
        await self._get_owned_track(track_id, user_id)
        lyrics = await self._repo.get_by_track_id(track_id)
        if not lyrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lyrics not found",
            )
        removed = await self._repo.delete_translation(
            track_lyrics_id=lyrics.id,
            language_code=language_code,
        )
        if removed:
            await self._session.commit()
        return removed

    async def trigger_auto_generation(
        self,
        track_id: int,
        user_id: int,
        with_sync: bool = False,
        bypass_cache: bool = False,
    ) -> str:
        from dotsound_private_core.services.asr_policy import (
            TIER_CATALOG_ONLY,
            skipped_tiers_for_existing_text_sync,
        )

        from app.models.lyrics_job import LyricsJob
        from app.services.compute_router import (
            get_routing_mode,
        )
        from app.services.lyrics_cascade import (
            start_cascade,
        )
        from app.services.lyrics_worker import (
            set_lyrics_progress,
        )

        track = await self._get_owned_track(track_id, user_id)
        progress_id = uuid.uuid4().hex

        lyrics_row = await self._repo.get_by_track_id(track_id)
        existing_text = (
            (lyrics_row.plain_text or "").strip()
            if lyrics_row is not None
            else ""
        )
        existing_has_sync = (
            has_nonempty_synced_lines(lyrics_row.synced_lines)
            if lyrics_row is not None
            else False
        )
        reuse_existing_text = bool(
            with_sync and existing_text and not existing_has_sync
        )
        if existing_text and not reuse_existing_text:
            await set_lyrics_progress(
                progress_id,
                stage="saving",
                terminal_state="found",
                percent=100,
                log_line="existing lyrics kept; auto-detection skipped",
            )
            logger.info(
                "lyrics_auto_skip_existing_text",
                track_id=track_id,
                has_sync=existing_has_sync,
            )
            return progress_id
        if reuse_existing_text:
            assert lyrics_row is not None
            from app.services.lyrics_worker import (
                set_cached_lyrics_result,
            )

            bypass_cache = False
            try:
                await set_cached_lyrics_result(
                    track.artist or "",
                    track.title or "",
                    {
                        "text": lyrics_row.plain_text,
                        "synced_lines": None,
                        "sync_quality": None,
                        "sync_profile": None,
                        "source_name": lyrics_row.source_name,
                        "sync_source_name": None,
                        "preserve_existing_text": True,
                    },
                )
            except Exception:
                logger.warning(
                    "lyrics_auto_existing_text_cache_seed_failed",
                    track_id=track_id,
                    exc_info=True,
                )

        skip_tiers = skipped_tiers_for_existing_text_sync(
            with_sync=with_sync,
            has_existing_text=bool(existing_text),
            has_existing_sync=existing_has_sync,
        )
        skip_reason = (
            "existing_text_needs_timing" if skip_tiers else None
        )
        urgent_remote_sync = bool(
            with_sync and (track.file_key or getattr(track, "sc_url", None))
        )
        if urgent_remote_sync and TIER_CATALOG_ONLY not in skip_tiers:
            skip_tiers = (*skip_tiers, TIER_CATALOG_ONLY)
            skip_reason = "manual_sync_prefers_remote_worker"

        mode = await get_routing_mode(self._session)
        if mode == "disabled":
            raise HTTPException(
                status_code=503,
                detail="lyrics_routing_disabled",
            )

        job = LyricsJob(
            id=f"lj_{uuid.uuid4().hex[:16]}",
            track_id=track_id,
            progress_id=progress_id,
            requested_by_user_id=user_id,
            profile="catalog_only",
            status="queued",
            queue_priority=(
                _URGENT_REMOTE_SYNC_PRIORITY if urgent_remote_sync else 0
            ),
            request_with_sync=with_sync,
            request_bypass_cache=bypass_cache,
            request_align_existing_text=reuse_existing_text,
        )
        self._session.add(job)
        await self._session.flush()

        active_tier = await start_cascade(
            self._session,
            job=job,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
            skip_tiers=skip_tiers,
            skip_reason=skip_reason,
        )
        await self._session.commit()

        await set_lyrics_progress(
            progress_id,
            stage="queued",
            log_line=(
                "cascade started, active tier="
                f"{active_tier}"
                f" (with_sync={with_sync},"
                f" bypass_cache={bypass_cache})"
            ),
            percent=2,
        )
        try:
            from app.services.lyrics_eta import (
                publish_initial_eta,
            )

            await publish_initial_eta(progress_id, job.profile)
        except Exception:
            logger.debug(
                "lyrics_eta_seed_failed",
                progress_id=progress_id,
            )
        logger.info(
            "lyrics_auto_triggered",
            track_id=track_id,
            job_id=job.id,
            active_tier=active_tier,
            profile=job.profile,
            progress_id=progress_id,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
        )
        return progress_id

    async def enqueue_background_lyrics(
        self,
        track_id: int,
        *,
        requested_by_user_id: int | None,
        with_sync: bool = True,
        bypass_cache: bool = False,
        profile: str = "catalog_only",
        force_sync_existing_text: bool = False,
    ) -> str | None:
        from app.models.lyrics_job import LyricsJob
        from app.services.compute_router import (
            get_routing_mode,
        )
        from app.services.lyrics_cascade import (
            start_cascade,
        )
        from app.services.lyrics_worker import (
            set_lyrics_progress,
        )

        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            logger.warning(
                "lyrics_background_skip_missing_track",
                track_id=track_id,
            )
            return None

        lyrics_row = await self._repo.get_by_track_id(track_id)
        existing_text = (
            (lyrics_row.plain_text or "").strip()
            if lyrics_row is not None
            else ""
        )
        existing_has_sync = (
            has_nonempty_synced_lines(lyrics_row.synced_lines)
            if lyrics_row is not None
            else False
        )
        sync_existing_text = bool(
            with_sync
            and force_sync_existing_text
            and existing_text
            and not existing_has_sync
        )
        if existing_text and not sync_existing_text:
            logger.debug(
                "lyrics_background_skip_has_plain_text",
                track_id=track_id,
                has_sync=existing_has_sync,
            )
            return None
        if sync_existing_text:
            assert lyrics_row is not None
            from app.services.lyrics_worker import (
                set_cached_lyrics_result,
            )

            bypass_cache = False
            try:
                await set_cached_lyrics_result(
                    track.artist or "",
                    track.title or "",
                    {
                        "text": lyrics_row.plain_text,
                        "synced_lines": None,
                        "sync_quality": None,
                        "sync_profile": None,
                        "source_name": lyrics_row.source_name,
                        "sync_source_name": None,
                        "preserve_existing_text": True,
                    },
                )
            except Exception:
                logger.warning(
                    "lyrics_background_existing_text_cache_seed_failed",
                    track_id=track_id,
                    exc_info=True,
                )

        mode = await get_routing_mode(self._session)
        if mode == "disabled":
            logger.info(
                "lyrics_background_skip_routing_disabled",
                track_id=track_id,
            )
            return None

        busy = (
            await self._session.execute(
                select(LyricsJob.id).where(
                    LyricsJob.track_id == track_id,
                    LyricsJob.status.in_(("queued", "running")),
                )
            )
        ).scalar_one_or_none()
        if busy is not None:
            logger.debug(
                "lyrics_background_skip_active_job",
                track_id=track_id,
                existing_job_id=busy,
            )
            return None

        progress_id = uuid.uuid4().hex
        job = LyricsJob(
            id=f"lj_{uuid.uuid4().hex[:16]}",
            track_id=track_id,
            progress_id=progress_id,
            requested_by_user_id=requested_by_user_id,
            profile=profile,
            status="queued",
            request_with_sync=with_sync,
            request_bypass_cache=bypass_cache,
            request_align_existing_text=sync_existing_text,
        )
        self._session.add(job)
        await self._session.flush()

        skip_tiers: tuple[str, ...] = ()
        skip_reason: str | None = None
        if sync_existing_text:
            from dotsound_private_core.services.asr_policy import (
                skipped_tiers_for_existing_text_sync,
            )

            skip_tiers = skipped_tiers_for_existing_text_sync(
                with_sync=with_sync,
                has_existing_text=True,
                has_existing_sync=False,
            )
            skip_reason = (
                "existing_text_needs_timing" if skip_tiers else None
            )

        active_tier = await start_cascade(
            self._session,
            job=job,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
            skip_tiers=skip_tiers,
            skip_reason=skip_reason,
        )
        await self._session.commit()

        await set_lyrics_progress(
            progress_id,
            stage="queued",
            log_line=(
                "ingest cascade started, active tier="
                f"{active_tier}"
                f" (with_sync={with_sync},"
                f" bypass_cache={bypass_cache})"
            ),
            percent=2,
        )
        try:
            from app.services.lyrics_eta import (
                publish_initial_eta,
            )

            await publish_initial_eta(progress_id, job.profile)
        except Exception:
            logger.debug(
                "lyrics_eta_seed_failed",
                progress_id=progress_id,
            )
        logger.info(
            "lyrics_background_enqueued",
            track_id=track_id,
            job_id=job.id,
            active_tier=active_tier,
            profile=job.profile,
            requested_by=requested_by_user_id,
            force_sync_existing_text=sync_existing_text,
        )
        return progress_id

    async def redefine_lyrics(
        self,
        track_id: int,
        user_id: int,
        with_sync: bool = False,
        bypass_cache: bool = False,
    ) -> str:
        """Delete existing lyrics and re-run detection from scratch.

        The (artist, title) Redis search cache is ALWAYS invalidated
        here so a real re-detection happens instead of silently
        re-loading the previously cached provider answer.

        ``bypass_cache`` additionally instructs the worker to skip
        any cache read on this run (admin / debug force-mode).

        Returns: progress_id for tracking the new generation task
        """
        from app.services.lyrics_worker import (
            invalidate_cached_lyrics_for_track,
            set_cached_lyrics_result,
        )

        track = await self._get_owned_track(track_id, user_id)
        await self._session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(lyrics_catalog_miss_at=None)
        )
        await self._session.flush()
        existing = await self._repo.get_by_track_id(track_id)

        artist = track.artist or ""
        title = track.title or ""

        try:
            await invalidate_cached_lyrics_for_track(artist, title)
            logger.info(
                "lyrics_redefine_cache_invalidated",
                track_id=track_id,
            )
        except Exception:
            logger.exception(
                "lyrics_redefine_cache_invalidate_failed",
                track_id=track_id,
            )

        use_existing_text_for_sync = bool(
            with_sync
            and existing is not None
            and bool((existing.plain_text or "").strip())
        )

        if use_existing_text_for_sync:
            assert existing is not None
            existing.synced_lines = None
            existing.sync_quality = None
            existing.sync_profile = None
            existing.sync_source_name = None
            await self._session.flush()
            try:
                await set_cached_lyrics_result(
                    artist,
                    title,
                    {
                        "text": existing.plain_text,
                        "synced_lines": None,
                        "sync_quality": None,
                        "sync_profile": None,
                        "source_name": existing.source_name,
                        "sync_source_name": None,
                    },
                )
                logger.info(
                    "lyrics_redefine_reuse_existing_text",
                    track_id=track_id,
                )
            except Exception:
                logger.exception(
                    "lyrics_redefine_cache_seed_failed",
                    track_id=track_id,
                )
        else:
            await self._repo.delete_by_track_id(track_id)
            await self._session.commit()
            logger.info(
                "lyrics_redefine_deleted",
                track_id=track_id,
                artist=artist,
                title=title,
                bypass_cache=bypass_cache,
            )

        progress_id = await self.trigger_auto_generation(
            track_id=track_id,
            user_id=user_id,
            with_sync=with_sync,
            bypass_cache=(
                False if use_existing_text_for_sync else bypass_cache
            ),
        )
        logger.info(
            "lyrics_redefine_triggered",
            track_id=track_id,
            progress_id=progress_id,
            bypass_cache=bypass_cache,
            reused_existing_text=use_existing_text_for_sync,
        )
        return progress_id

    async def cancel_auto_generation(
        self,
        track_id: int,
        user_id: int,
        progress_id: str,
    ) -> bool:
        """Request cancellation of a running lyrics detection task.

        Returns: True if cancellation flag was set, False if
        task already completed.
        """
        await self._get_owned_track(track_id, user_id)

        from app.core.redis import get_redis_client
        from app.services.lyrics_worker import (
            CANCEL_KEY_PREFIX,
            set_lyrics_progress,
        )

        redis = get_redis_client()
        await redis.set(f"{CANCEL_KEY_PREFIX}{progress_id}", "1", ex=600)
        await set_lyrics_progress(
            progress_id,
            stage="cancelling",
            log_line="cancellation requested by user",
        )
        logger.info(
            "lyrics_cancel_requested",
            track_id=track_id,
            progress_id=progress_id,
        )
        return True
