from datetime import datetime
from enum import Enum
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str | None
    genre: str | None = None
    file_size_bytes: int | None = None
    processing_status: str = "active"
    duration_seconds: int | None
    cover_key: str | None = None
    description: str | None = None
    video_key: str | None = None
    video_processing_status: str | None = None
    video_thumbnail_key: str | None = None
    play_count: int
    is_active: bool
    is_public: bool = True
    source: str = "internal"
    sc_url: str | None = None
    sc_uri: str | None = None
    uploaded_by_id: int | None = None
    album_id: int | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_url(self) -> str | None:
        if not self.cover_key:
            return None
        return f"/api/v1/tracks/cover_proxy?key={quote(self.cover_key, safe='')}"


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
    genre: str | None = None
    processing_status: str = "processing"
    file_key: str | None
    cover_key: str | None
    duration_seconds: int | None
    source: str = "internal"
    is_public: bool = True
    created_at: datetime


class TrackUpdateRequest(BaseModel):
    title: str | None = Field(
        None, max_length=256, min_length=1
    )
    artist: str | None = Field(None, max_length=256)
    genre: str | None = Field(None, max_length=100)
    description: str | None = Field(
        None, max_length=2000
    )
    is_public: bool | None = None


class StreamResponse(BaseModel):
    track_id: int
    url: str
    stream_type: str = Field(
        default="direct",
        description="direct or hls",
    )
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


class PlaybackMode(str, Enum):
    sequential = "sequential"
    shuffle = "shuffle"
    repeat_one = "repeat_one"


class AdjacentTracksResponse(BaseModel):
    prev_id: int | None = None
    next_id: int | None = None


class TrackQueueResponse(BaseModel):
    next_tracks: list[TrackResponse]
