from pydantic import BaseModel, EmailStr


class LinkEmailRequest(BaseModel):
    email: EmailStr


class LinkEmailVerifyRequest(BaseModel):
    token: str


class LinkTelegramRequest(BaseModel):
    code: str
    telegram_id: int


class MergeRequest(BaseModel):
    source_account_token: str


class LinkStatusResponse(BaseModel):
    telegram_linked: bool
    email_linked: bool
    email: str | None = None
    telegram_username: str | None = None


class LinkConflictResponse(BaseModel):
    error: str
    message: str
    has_telegram: bool = False
    has_email: bool = False
    can_merge: bool = False
