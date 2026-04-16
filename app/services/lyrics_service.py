import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.repositories.lyrics import LyricsRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.lyrics_worker import (
    generate_lyrics_task,
)

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
    ) -> str:
        import uuid

        from app.services.lyrics_worker import (
            set_lyrics_progress,
        )

        await self._get_owned_track(track_id, user_id)
        progress_id = uuid.uuid4().hex
        task = await generate_lyrics_task.kiq(
            track_id=track_id,
            with_sync=with_sync,
            progress_id=progress_id,
        )
        await set_lyrics_progress(
            progress_id,
            "queued",
            f"task queued: taskiq_id={task.task_id}",
        )
        logger.info(
            "lyrics_auto_triggered",
            track_id=track_id,
            task_id=task.task_id,
            progress_id=progress_id,
            with_sync=with_sync,
        )
        return progress_id

    async def redefine_lyrics(
        self,
        track_id: int,
        user_id: int,
        with_sync: bool = False,
    ) -> str:
        """Delete existing lyrics and re-run detection from scratch.

        Returns: progress_id for tracking the new generation task
        """
        await self._get_owned_track(track_id, user_id)

        # Delete existing lyrics
        await self._repo.delete_by_track_id(track_id)
        await self._session.commit()
        logger.info("lyrics_redefine_deleted", track_id=track_id)

        # Trigger new auto-generation
        progress_id = await self.trigger_auto_generation(
            track_id=track_id,
            user_id=user_id,
            with_sync=with_sync,
        )
        logger.info(
            "lyrics_redefine_triggered",
            track_id=track_id,
            progress_id=progress_id,
        )
        return progress_id

    async def cancel_auto_generation(
        self,
        track_id: int,
        user_id: int,
        progress_id: str,
    ) -> bool:
        """Request cancellation of a running lyrics detection task.

        Returns: True if cancellation flag was set, False if task already completed
        """
        await self._get_owned_track(track_id, user_id)

        from app.config import settings
        from app.services.lyrics_worker import set_lyrics_progress
        from redis.asyncio import Redis

        redis = Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        try:
            # Set cancellation flag
            await redis.set(
                f"lyrics:cancel:{progress_id}", "1", ex=600
            )
            await set_lyrics_progress(
                progress_id,
                "cancelling",
                "cancellation requested by user",
            )
            logger.info(
                "lyrics_cancel_requested",
                track_id=track_id,
                progress_id=progress_id,
            )
            return True
        finally:
            await redis.aclose()
