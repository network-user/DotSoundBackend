from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackResponse


class PlaylistCreate(BaseModel):
    name: str = Field(max_length=256)
    is_public: bool = True


class PlaylistUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    is_public: bool | None = None


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    created_at: datetime


class PlaylistWithTracksResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    created_at: datetime
    tracks: list[TrackResponse] = []


class PlaylistAddTrack(BaseModel):
    track_id: int
    position: int = Field(default=0, ge=0)


class PlaylistTrackOrderRequest(BaseModel):
    track_ids: list[int] = Field(min_length=1)
