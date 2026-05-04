"""Pydantic schemas shared across admin sub-modules."""

from datetime import datetime
from typing import Literal

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
    reason_type: str
    contact_email: str | None
    rightsholder_name: str | None
    proof_url: str | None
    is_resolved: bool
    created_at: datetime


class AdminComplaintUpdateRequest(BaseModel):
    action: Literal["accept", "dismiss", "in_progress"]
    note: str | None = Field(None, max_length=500)


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


class TrackContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    content: str | None
    status: str
    fetched_at: datetime | None


class TrackContextUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class BatchPromptRequest(BaseModel):
    track_ids: list[int] = Field(..., min_length=1, max_length=200)


class BatchPromptResponse(BaseModel):
    prompt: str
    track_count: int


class SinglePromptResponse(BaseModel):
    prompt: str
    language: str


class BatchImportRequest(BaseModel):
    raw_response: str = Field(..., min_length=2, max_length=500_000)


class BatchImportResponse(BaseModel):
    imported: int
    errors: list[str]


class AdminAlbumListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    owner_id: int
    is_public: bool
    created_at: datetime
    track_count: int


class AdminAlbumListResponse(BaseModel):
    items: list[AdminAlbumListItem]
    total: int
    page: int
    size: int


class AdminAlbumDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    cover_key: str | None = None
    owner_id: int
    is_public: bool
    created_at: datetime
    tracks: list[AdminTrackResponse]


class AdminAlbumPatchRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool | None = None
    owner_id: int | None = None


class AdminAlbumReorderRequest(BaseModel):
    track_ids: list[int] = Field(default_factory=list)


class AdminPlaylistListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    created_at: datetime
    track_count: int


class AdminPlaylistListResponse(BaseModel):
    items: list[AdminPlaylistListItem]
    total: int
    page: int
    size: int


class AdminPlaylistDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_public: bool
    created_at: datetime
    tracks: list[AdminTrackResponse]


class AdminPlaylistPatchRequest(BaseModel):
    name: str | None = Field(None, max_length=256)
    is_public: bool | None = None
    owner_id: int | None = None


class AdminPlaylistReorderRequest(BaseModel):
    track_ids: list[int] = Field(default_factory=list)
