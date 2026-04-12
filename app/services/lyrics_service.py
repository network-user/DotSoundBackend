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

    async def delete_lyrics(self, track_id: int, user_id: int) -> bool:
        await self._get_owned_track(track_id, user_id)
        removed = await self._repo.delete_by_track_id(track_id)
        if removed:
            await self._session.commit()
        return removed
