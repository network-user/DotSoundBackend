from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    telegram_id: int | None = None
    email: str | None = None
    username: str | None = None
    first_name: str
    last_name: str | None = None
    auth_provider: str = "telegram"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int | None = None
    username: str | None = None
    first_name: str
    last_name: str | None = None
    display_name: str | None = None
    avatar_key: str | None = None
    email: str | None = None
    email_verified: bool = False
    auth_provider: str = "telegram"
    totp_enabled: bool = False
    is_active: bool
    is_admin: bool = False
    locale: str | None = None
    profile_visibility: Literal["public", "followers_only", "hidden"] = (
        "public"
    )
    profile_access: Literal["full", "limited"] = "full"
    created_at: datetime


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r"^[^\s].*[^\s]$|^[^\s]$"
    )
    locale: str | None = Field(
        None, max_length=10
    )
    profile_visibility: (
        Literal["public", "followers_only", "hidden"] | None
    ) = None


class DeleteAccountRequest(BaseModel):
    confirmation: str = Field(
        ..., min_length=1, max_length=20
    )


class DeletionStatusResponse(BaseModel):
    pending: bool
    deleted_at: datetime | None = None
    grace_until: datetime | None = None


class TopGenreItem(BaseModel):
    genre: str
    completed_listens: int = Field(ge=0)


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
    total_likes: int = 0
    followers_count: int = 0
    following_count: int = 0
    top_tracks: list[TrackStatsItem] = Field(
        description="Top 5 most played tracks"
    )


class ShareCardResponse(BaseModel):
    """Public-safe payload for rendering a shareable profile card.

    Used by the frontend to build a preview card with QR / link
    (Telegram Mini App or web). No private fields are exposed.
    """

    user_id: int
    display_name: str
    username: str | None = None
    avatar_url: str | None = None
    profile_url: str
    deep_link: str | None = Field(
        default=None,
        description=(
            "Telegram t.me deep-link to open the profile inside the bot"
        ),
    )
    total_tracks: int = Field(ge=0, default=0)
    total_plays: int = Field(ge=0, default=0)
    total_likes: int = Field(ge=0, default=0)
    followers_count: int = Field(ge=0, default=0)
    top_track_titles: list[str] = Field(default_factory=list)


class UserTopResponse(BaseModel):
    window: str
    top_tracks: list[TrackStatsItem] = Field(
        default_factory=list,
    )
    top_genres: list[TopGenreItem] = Field(
        default_factory=list,
    )
