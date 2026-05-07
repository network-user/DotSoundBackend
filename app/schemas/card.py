from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.track import TrackPlaybackVariantBrief


class TrackAlbumInfo(BaseModel):
    id: int
    title: str
    cover_key: str | None = None


class TrackCardResponse(BaseModel):
    id: int
    title: str
    artist: str | None = None
    genre: str | None = None
    duration_seconds: int | None = None
    play_count: int
    cover_url: str | None = None
    created_at: datetime
    album: TrackAlbumInfo | None = None
    has_lyrics: bool = False
    playback_variants: list[TrackPlaybackVariantBrief] = Field(
        default_factory=list,
    )
