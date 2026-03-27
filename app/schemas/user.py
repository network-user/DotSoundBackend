from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str
    last_name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    is_active: bool
    created_at: datetime
