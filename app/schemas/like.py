from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.track import TrackResponse


class LikeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    track_id: int
    created_at: datetime


class LikeToggleResponse(BaseModel):
    track_id: int
    liked: bool


class UserLikesResponse(BaseModel):
    items: list[TrackResponse]
    total: int


class DislikeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    track_id: int
    created_at: datetime


class DislikeToggleResponse(BaseModel):
    track_id: int
    disliked: bool
