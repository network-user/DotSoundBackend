from urllib.parse import quote

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.lyrics import LyricsRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.schemas.card import TrackAlbumInfo, TrackAuthorInfo, TrackCardResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class CardService:
    def __init__(self, session: AsyncSession) -> None:
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._lyrics_repo = LyricsRepository(session)

    async def get_card(
        self,
        track_id: int,
        requester_id: int | None = None,
    ) -> TrackCardResponse | None:
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            return None
        is_owner = (
            requester_id
            and track.uploaded_by_id == requester_id
        )
        if not track.is_public and not is_owner:
            return None

        author = None
        if track.uploaded_by_id:
            user = await self._user_repo.get_by_id(track.uploaded_by_id)
            if user:
                author = TrackAuthorInfo(
                    id=user.id,
                    display_name=user.display_name,
                    username=user.username,
                    avatar_key=user.avatar_key,
                )

        album_info = None
        if track.album_id:
            from app.repositories.album import AlbumRepository
            album_repo = AlbumRepository(self._track_repo._session)
            album = await album_repo.get_by_id(track.album_id)
            if album:
                album_info = TrackAlbumInfo(
                    id=album.id,
                    title=album.title,
                    cover_key=album.cover_key,
                )

        lyrics = await self._lyrics_repo.get_by_track_id(track_id)

        cover_url = None
        if track.cover_key:
            cover_url = f"/api/v1/tracks/cover_proxy?key={quote(track.cover_key, safe='')}"

        logger.debug("card_built", track_id=track_id)
        return TrackCardResponse(
            id=track.id,
            title=track.title,
            artist=track.artist,
            genre=track.genre,
            duration_seconds=track.duration_seconds,
            play_count=track.play_count,
            cover_url=cover_url,
            created_at=track.created_at,
            author=author,
            album=album_info,
            has_lyrics=lyrics is not None,
        )
