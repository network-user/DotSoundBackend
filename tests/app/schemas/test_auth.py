import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    TelegramAuthRequest,
    TokenResponse,
)


def test_telegram_auth_request_valid() -> None:
    req = TelegramAuthRequest(init_data="abc123")
    assert req.init_data == "abc123"


def test_telegram_auth_request_missing_init_data() -> None:
    with pytest.raises(ValidationError):
        TelegramAuthRequest()


def test_telegram_auth_request_empty_string() -> None:
    req = TelegramAuthRequest(init_data="")
    assert req.init_data == ""


def test_token_response_valid() -> None:
    resp = TokenResponse(
        access_token="tok",
        user_id=1,
        is_admin=False,
    )
    assert resp.access_token == "tok"
    assert resp.token_type == "bearer"
    assert resp.user_id == 1
    assert resp.is_admin is False


def test_token_response_default_token_type() -> None:
    resp = TokenResponse(
        access_token="t",
        user_id=42,
        is_admin=True,
    )
    assert resp.token_type == "bearer"


def test_token_response_custom_token_type() -> None:
    resp = TokenResponse(
        access_token="t",
        token_type="custom",
        user_id=1,
        is_admin=False,
    )
    assert resp.token_type == "custom"


def test_token_response_missing_required() -> None:
    with pytest.raises(ValidationError):
        TokenResponse(access_token="t")


def test_token_response_wrong_type_user_id() -> None:
    with pytest.raises(ValidationError):
        TokenResponse(
            access_token="t",
            user_id="abc",
            is_admin=False,
        )
