from datetime import datetime

from pydantic import BaseModel, Field


class SnippetCreateRequest(BaseModel):
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=1)


class SnippetOut(BaseModel):
    id: int
    track_id: int
    status: str
    file_key: str | None
    start_ms: int
    end_ms: int
    error_message: str | None
    created_at: datetime
