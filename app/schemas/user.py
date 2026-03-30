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
    display_name: str | None = None
    avatar_key: str | None = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=128)


class AvatarResponse(BaseModel):
    avatar_url: str


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
