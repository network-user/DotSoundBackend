from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str | None
    duration_seconds: int | None
    cover_key: str | None = None
    play_count: int
    is_active: bool
    created_at: datetime


class TrackListResponse(BaseModel):
    items: list[TrackResponse]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)


class TrackUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str | None
    file_key: str
    cover_key: str | None
    duration_seconds: int | None
    created_at: datetime


class StreamResponse(BaseModel):
    track_id: int
    url: str
    expires_in: int = Field(
        default=3600, description="URL TTL in seconds"
    )


class PlayResponse(BaseModel):
    track_id: int
    play_count: int
