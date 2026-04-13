import pytest
from pydantic import ValidationError

from app.schemas.auth_email import (
    EmailAuthRequest,
    EmailAuthResponse,
    EmailVerifyRequest,
    EmailVerifyResponse,
    TwoFAConfirmRequest,
    TwoFAEmailFallbackRequest,
    TwoFASetupResponse,
    TwoFAVerifyRequest,
)


def test_email_auth_request_valid() -> None:
    req = EmailAuthRequest(email="user@example.com")
    assert req.email == "user@example.com"


def test_email_auth_request_invalid_email() -> None:
    with pytest.raises(ValidationError):
        EmailAuthRequest(email="not-an-email")


def test_email_auth_request_missing() -> None:
    with pytest.raises(ValidationError):
        EmailAuthRequest()


def test_email_auth_response_default() -> None:
    resp = EmailAuthResponse()
    assert resp.message == "Check your inbox"


def test_email_auth_response_custom() -> None:
    resp = EmailAuthResponse(message="Sent")
    assert resp.message == "Sent"


def test_email_verify_request_valid() -> None:
    req = EmailVerifyRequest(token="abc")
    assert req.token == "abc"


def test_email_verify_request_missing() -> None:
    with pytest.raises(ValidationError):
        EmailVerifyRequest()


def test_email_verify_response_defaults() -> None:
    resp = EmailVerifyResponse()
    assert resp.access_token is None
    assert resp.token_type == "bearer"
    assert resp.user_id is None
    assert resp.is_admin is False
    assert resp.requires_2fa is False
    assert resp.session_token is None


def test_email_verify_response_full() -> None:
    resp = EmailVerifyResponse(
        access_token="tok",
        user_id=5,
        is_admin=True,
        requires_2fa=True,
        session_token="sess",
    )
    assert resp.access_token == "tok"
    assert resp.user_id == 5
    assert resp.is_admin is True
    assert resp.requires_2fa is True
    assert resp.session_token == "sess"


def test_two_fa_verify_request_with_code() -> None:
    req = TwoFAVerifyRequest(
        session_token="s", code="123456"
    )
    assert req.code == "123456"
    assert req.backup_code is None


def test_two_fa_verify_request_with_backup() -> None:
    req = TwoFAVerifyRequest(
        session_token="s", backup_code="bk"
    )
    assert req.backup_code == "bk"
    assert req.code is None


def test_two_fa_verify_request_missing_session() -> None:
    with pytest.raises(ValidationError):
        TwoFAVerifyRequest(code="123456")


def test_two_fa_setup_response_valid() -> None:
    resp = TwoFASetupResponse(
        otpauth_uri="otpauth://totp/app?secret=X",
        qr_code_base64="base64data",
        backup_codes=["a", "b", "c"],
    )
    assert len(resp.backup_codes) == 3


def test_two_fa_setup_response_missing() -> None:
    with pytest.raises(ValidationError):
        TwoFASetupResponse(otpauth_uri="x")


def test_two_fa_setup_response_empty_codes() -> None:
    resp = TwoFASetupResponse(
        otpauth_uri="uri",
        qr_code_base64="qr",
        backup_codes=[],
    )
    assert resp.backup_codes == []


def test_two_fa_confirm_request_valid() -> None:
    req = TwoFAConfirmRequest(code="654321")
    assert req.code == "654321"


def test_two_fa_confirm_request_missing() -> None:
    with pytest.raises(ValidationError):
        TwoFAConfirmRequest()


def test_two_fa_email_fallback_valid() -> None:
    req = TwoFAEmailFallbackRequest(
        session_token="tok"
    )
    assert req.session_token == "tok"


def test_two_fa_email_fallback_missing() -> None:
    with pytest.raises(ValidationError):
        TwoFAEmailFallbackRequest()
