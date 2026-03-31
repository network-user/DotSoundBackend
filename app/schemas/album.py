from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackResponse


class AlbumCreateRequest(BaseModel):
    title: str = Field(max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool = True


class AlbumUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool | None = None


class AlbumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    cover_key: str | None = None
    owner_id: int
    is_public: bool
    created_at: datetime


class AlbumWithTracksResponse(AlbumResponse):
    tracks: list[TrackResponse] = []
