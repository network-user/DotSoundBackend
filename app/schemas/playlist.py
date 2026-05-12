from datetime import datetime
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.track import TrackResponse


class PlaylistCreate(BaseModel):
    name: str = Field(max_length=256)
    is_public: bool = True
    description: str | None = Field(None, max_length=512)


class PlaylistUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    is_public: bool | None = None
    description: str | None = Field(None, max_length=512)


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    playlist_type: str = "user"
    is_featured: bool = False
    source_url: str | None = None
    cover_key: str | None = None
    cover_auto_suppressed: bool = False
    collage_generated_at: datetime | None = None
    description: str | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_url(self) -> str | None:
        if not self.cover_key:
            return None
        return (
            f"/api/v1/tracks/cover_proxy?key="
            f"{quote(self.cover_key, safe='')}"
        )


class PlaylistWithTracksResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    playlist_type: str = "user"
    is_featured: bool = False
    source_url: str | None = None
    cover_key: str | None = None
    cover_auto_suppressed: bool = False
    collage_generated_at: datetime | None = None
    description: str | None = None
    created_at: datetime
    tracks: list[TrackResponse] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_url(self) -> str | None:
        if not self.cover_key:
            return None
        return (
            f"/api/v1/tracks/cover_proxy?key="
            f"{quote(self.cover_key, safe='')}"
        )


class PlaylistAddTrack(BaseModel):
    track_id: int
    position: int = Field(default=0, ge=0)


class PlaylistTrackOrderRequest(BaseModel):
    track_ids: list[int] = Field(min_length=1)
