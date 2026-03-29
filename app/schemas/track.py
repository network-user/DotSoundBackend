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
    is_public: bool = True
    source: str = "internal"
    sc_url: str | None = None
    sc_uri: str | None = None
    uploaded_by_id: int | None = None
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
    file_key: str | None
    cover_key: str | None
    duration_seconds: int | None
    source: str = "internal"
    is_public: bool = True
    created_at: datetime


class TrackUpdateRequest(BaseModel):
    is_public: bool | None = None


class StreamResponse(BaseModel):
    track_id: int
    url: str
    expires_in: int = Field(
        default=3600, description="URL TTL in seconds"
    )


class PlayResponse(BaseModel):
    track_id: int
    play_count: int


class SCSearchResult(BaseModel):
    sc_id: int
    title: str
    artist: str | None
    duration_seconds: int | None
    artwork_url: str | None
    sc_url: str
    sc_uri: str
