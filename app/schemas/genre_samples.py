from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackResponse


class GenrePreviewQueueResponse(BaseModel):
    items: list[TrackResponse]


class AdminGenreSampleCreateRequest(BaseModel):
    track_id: int = Field(ge=1)
    position: int = 0


class AdminGenreSampleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    genre: str
    track_id: int
    position: int
    curated: bool
    created_at: datetime


class AdminGenreSampleListResponse(BaseModel):
    items: list[AdminGenreSampleItem]
