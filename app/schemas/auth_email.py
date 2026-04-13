from pydantic import BaseModel, EmailStr


class EmailAuthRequest(BaseModel):
    email: EmailStr


class EmailAuthResponse(BaseModel):
    message: str = "Check your inbox"


class EmailVerifyRequest(BaseModel):
    token: str


class EmailVerifyResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user_id: int | None = None
    is_admin: bool = False
    requires_2fa: bool = False
    session_token: str | None = None


class TwoFAVerifyRequest(BaseModel):
    session_token: str
    code: str | None = None
    backup_code: str | None = None


class TwoFASetupResponse(BaseModel):
    otpauth_uri: str
    qr_code_base64: str
    backup_codes: list[str]


class TwoFAConfirmRequest(BaseModel):
    code: str


class TwoFAEmailFallbackRequest(BaseModel):
    session_token: str
