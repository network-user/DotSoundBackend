from urllib.parse import quote

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.schemas.card import TrackAlbumInfo, TrackCardResponse
from app.services.track_playback_health_service import (
    is_track_playback_suppressed,
)
from app.services.track_response_build import build_track_response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class CardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._track_repo = TrackRepository(session)

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
            and track.catalog_type == "ugc"
        )
        if not track.is_public and not is_owner:
            return None
        if is_track_playback_suppressed(track) and not is_owner:
            return None

        album_info = None
        if track.album_id:
            from app.repositories.album import AlbumRepository

            album_repo = AlbumRepository(self._session)
            album = await album_repo.get_by_id(track.album_id)
            if album:
                album_info = TrackAlbumInfo(
                    id=album.id,
                    title=album.title,
                    cover_key=album.cover_key,
                )

        cover_key = track.cover_key
        if not cover_key and album_info and album_info.cover_key:
            cover_key = album_info.cover_key
        cover_url = None
        if cover_key:
            cover_url = (
                f"/api/v1/tracks/cover_proxy?key={quote(cover_key, safe='')}"
            )

        logger.debug("card_built", track_id=track_id)
        enriched = await build_track_response(self._session, track)
        return TrackCardResponse(
            id=track.id,
            title=track.title,
            artist=track.artist,
            genre=track.genre,
            duration_seconds=track.duration_seconds,
            play_count=track.play_count,
            cover_url=cover_url,
            created_at=track.created_at,
            album=album_info,
            has_lyrics=enriched.has_lyrics,
            playback_variants=enriched.playback_variants,
        )
