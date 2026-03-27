from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str | None
    duration_seconds: int | None
    play_count: int
    is_active: bool
    created_at: datetime


class TrackListResponse(BaseModel):
    items: list[TrackResponse]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)
