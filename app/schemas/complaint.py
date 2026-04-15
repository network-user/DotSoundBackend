from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ComplaintCreate(BaseModel):
    track_id: int
    reason: str = Field(
        min_length=10, max_length=1000
    )
    reason_type: str = Field(default="other")
    contact_email: EmailStr | None = None
    rightsholder_name: str | None = Field(
        None, max_length=255
    )
    proof_url: str | None = Field(
        None, max_length=2000
    )


class ComplaintResponse(BaseModel):
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


class ComplaintSubmitResponse(BaseModel):
    complaint: ComplaintResponse
    track_hidden: bool
