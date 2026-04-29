from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackResponse


class LikeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    track_id: int
    created_at: datetime


class LikeToggleResponse(BaseModel):
    track_id: int
    liked: bool
    playback_variant_track_ids: list[int] = Field(default_factory=list)


class LikedTrackResponse(TrackResponse):
    liked_at: datetime


class UserLikesResponse(BaseModel):
    items: list[LikedTrackResponse]
    total: int
    page: int = 1
    has_more: bool = False


class DislikeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    track_id: int
    created_at: datetime


class DislikeToggleResponse(BaseModel):
    track_id: int
    disliked: bool
    playback_variant_track_ids: list[int] = Field(default_factory=list)
