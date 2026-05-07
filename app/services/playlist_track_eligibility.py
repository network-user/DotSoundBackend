from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.user import UserRepository
from app.services.track_service import TrackService


def _catalog_row_is_playable(track: Track) -> bool:
    if track.file_key is not None:
        return True
    return track.access_mode in (
        "third_party_stream",
        "official_embed",
    )


async def ensure_track_addable_to_user_playlist(
    session: AsyncSession,
    *,
    track_id: int,
    playlist_owner_id: int,
) -> Track:
    owners = UserRepository(session)
    owner = await owners.get_by_id(playlist_owner_id)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist owner not found",
        )
    ts = TrackService(session)
    track = await ts.get_track(track_id, viewer=owner)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if not _catalog_row_is_playable(track):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Track is not playable",
        )
    return track
