from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str = Field(..., max_length=512)
    mime: str = Field(..., max_length=64)
    total_size: int = Field(..., gt=0)
    audio_hash: str | None = Field(None, max_length=64)
    title: str = Field(..., max_length=256)
    artist: str | None = Field(None, max_length=256)
    use_profile_artist: bool = False
    genre: str | None = Field(None, max_length=100)
    is_public: bool = True
    upload_terms_accepted: bool = False


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    expected_chunks: int
    expires_at: datetime
    completed_chunks: list[int] = Field(default_factory=list)


class UploadStatusResponse(BaseModel):
    upload_id: str
    status: str
    completed_chunks: list[int]
    expected_chunks: int
    expires_at: datetime
    track_id: int | None = None


class UploadCompleteResponse(BaseModel):
    track_id: int
    upload_id: str


class DuplicateCheckRequest(BaseModel):
    audio_hash: str = Field(..., min_length=64, max_length=64)
    size_bytes: int = Field(..., gt=0)


class DuplicateCheckResponse(BaseModel):
    exists: bool
    track_id: int | None = None
    title: str | None = None
    uploaded_at: datetime | None = None


class TrackEditContextResponse(BaseModel):
    track_id: int
    title: str
    artist: str | None
    genre: str | None
    description: str | None
    is_public: bool
    cover_key: str | None
    has_lyrics: bool
    is_processing: bool
    can_edit_artist: bool
    can_delete: bool
