from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class ComplaintCreate(BaseModel):
    track_id: int
    reason: str = Field(
        min_length=10, max_length=1000
    )
    reason_type: Literal[
        "other", "copyright", "neighboring_rights"
    ] = Field(default="other")
    contact_email: EmailStr | None = None
    rightsholder_name: str | None = Field(
        None, max_length=255
    )
    proof_url: str | None = Field(
        None, max_length=2000
    )

    @model_validator(mode="after")
    def validate_rightsholder_notice(self) -> "ComplaintCreate":
        if self.reason_type == "other":
            return self

        missing: list[str] = []
        if not self.contact_email:
            missing.append("contact_email")
        if not self.rightsholder_name:
            missing.append("rightsholder_name")
        if not self.proof_url:
            missing.append("proof_url")

        if missing:
            raise ValueError(
                "Rightsholder notice requires "
                + ", ".join(missing)
            )

        return self


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
