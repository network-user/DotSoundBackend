import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.repositories.lyrics import LyricsRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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

    async def _get_owned_track(self, track_id: int, user_id: int):
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )
        resolved_id = await self._resolve_user_id(user_id)
        if track.uploaded_by_id != resolved_id:
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
        self, track_id: int, user_id: int, synced_lines: list[dict]
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

    async def delete_lyrics(
        self, track_id: int, user_id: int
    ) -> bool:
        await self._get_owned_track(track_id, user_id)
        removed = await self._repo.delete_by_track_id(
            track_id
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
        import uuid

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

        await self._get_owned_track(track_id, user_id)
        progress_id = uuid.uuid4().hex

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
        )
        self._session.add(job)
        await self._session.flush()

        active_tier = await start_cascade(
            self._session,
            job=job,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
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

            await publish_initial_eta(
                progress_id, job.profile
            )
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
        )

        track = await self._get_owned_track(track_id, user_id)

        artist = track.artist or ""
        title = track.title or ""

        await self._repo.delete_by_track_id(track_id)
        await self._session.commit()
        logger.info(
            "lyrics_redefine_deleted",
            track_id=track_id,
            artist=artist,
            title=title,
            bypass_cache=bypass_cache,
        )

        try:
            await invalidate_cached_lyrics_for_track(
                artist, title
            )
            logger.info(
                "lyrics_redefine_cache_invalidated",
                track_id=track_id,
            )
        except Exception:
            logger.exception(
                "lyrics_redefine_cache_invalidate_failed",
                track_id=track_id,
            )

        progress_id = await self.trigger_auto_generation(
            track_id=track_id,
            user_id=user_id,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
        )
        logger.info(
            "lyrics_redefine_triggered",
            track_id=track_id,
            progress_id=progress_id,
            bypass_cache=bypass_cache,
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
        await redis.set(
            f"{CANCEL_KEY_PREFIX}{progress_id}", "1", ex=600
        )
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
