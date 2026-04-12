from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ComplaintCreate(BaseModel):
    track_id: int
    reason: str = Field(min_length=10, max_length=1000)
    contact_email: EmailStr | None = None


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    reported_by_user_id: int
    reason: str
    contact_email: str | None
    is_resolved: bool
    created_at: datetime


class ComplaintSubmitResponse(BaseModel):
    complaint: ComplaintResponse
    track_hidden: bool
