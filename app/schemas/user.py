from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str
    last_name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    is_active: bool
    created_at: datetime


class TrackStatsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str | None
    play_count: int
    cover_key: str | None = None


class UserStatsResponse(BaseModel):
    user_id: int
    total_tracks: int = Field(ge=0)
    total_plays: int = Field(ge=0)
    top_tracks: list[TrackStatsItem] = Field(
        description="Top 5 most played tracks"
    )
