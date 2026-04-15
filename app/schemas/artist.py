from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_key: str | None = None
    source: str = "internal"
    bio: str | None = None
    created_at: datetime


class ArtistListResponse(BaseModel):
    items: list[ArtistResponse]
    total: int


class ArtistDetailResponse(ArtistResponse):
    track_count: int = 0
