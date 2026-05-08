from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminInitStartResponse(BaseModel):
    secret_b32: str
    otpauth_uri: str
    ttl_seconds: int


class AdminInitConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)
    fingerprint: str = Field(
        ..., min_length=8, max_length=256
    )
    label: str | None = Field(None, max_length=128)


class AdminSessionPayload(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    jti: str
    refresh_jti: str
    session_id: int


class AdminInitConfirmResponse(BaseModel):
    backup_codes: list[str]
    device_id: int
    session: AdminSessionPayload


class AdminLoginRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)
    fingerprint: str = Field(
        ..., min_length=8, max_length=256
    )


class AdminLoginResponse(BaseModel):
    requires_device_approval: bool = False
    device_id: int | None = None
    session: AdminSessionPayload | None = None


class AdminDeviceApprovalRequest(BaseModel):
    device_id: int
    force_resend: bool = False


class AdminDeviceConfirmRequest(BaseModel):
    device_id: int
    email_code: str = Field(
        ..., min_length=4, max_length=10
    )
    totp_code: str = Field(
        ..., min_length=6, max_length=10
    )
    label: str | None = Field(None, max_length=128)


class AdminStepUpRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)
    action: str = Field(
        ..., min_length=2, max_length=64
    )


class AdminRefreshRequest(BaseModel):
    refresh_token: str


class AdminRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class AdminBackupCodesResponse(BaseModel):
    backup_codes: list[str]


class AdminDeviceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str | None
    fingerprint_hash_preview: str
    ip_first: str | None
    ua_first: str | None
    trusted_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime


class AdminDevicesListResponse(BaseModel):
    items: list[AdminDeviceItem]


class AdminAuthMetadata(BaseModel):
    is_admin: bool
    admin_init: bool
    admin_totp_enabled: bool
    has_backup_codes: bool


class AdminCsrfResponse(BaseModel):
    csrf: str


class AdminDisableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


class AdminMessageResponse(BaseModel):
    detail: str
