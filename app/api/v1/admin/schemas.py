"""Pydantic schemas shared across admin sub-modules."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackResponse
from app.schemas.user import UserResponse


class AdminTrackResponse(TrackResponse):
    uploaded_by_id: int | None = None
    is_active: bool = True


class AdminComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    reported_by_user_id: int
    reason: str
    contact_email: str | None
    is_resolved: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=128)
    is_active: bool | None = None
    is_admin: bool | None = None


class AdminTrackListResponse(BaseModel):
    items: list[AdminTrackResponse]
    total: int
    page: int
    size: int


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int


class AdminComplaintListResponse(BaseModel):
    items: list[AdminComplaintResponse]
    total: int
    page: int
    size: int
