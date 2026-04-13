from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_sender import (
    send_magic_link,
    send_totp_fallback_code,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.email_sender"


@patch(f"{_MOD}._send_async", new_callable=AsyncMock)
async def test_send_magic_link(
    mock_send: AsyncMock,
) -> None:
    await send_magic_link(
        "user@example.com",
        "https://example.com?token=abc",
    )

    mock_send.assert_awaited_once()
    params = mock_send.call_args[0][0]
    assert params["to"] == ["user@example.com"]
    assert "Sign in" in params["subject"]


@patch(f"{_MOD}._send_async", new_callable=AsyncMock)
async def test_send_totp_fallback_code(
    mock_send: AsyncMock,
) -> None:
    await send_totp_fallback_code(
        "user@example.com", "123456"
    )

    mock_send.assert_awaited_once()
    params = mock_send.call_args[0][0]
    assert "verification" in params["subject"]


@patch(
    f"{_MOD}._send_async",
    new_callable=AsyncMock,
    side_effect=Exception("SMTP error"),
)
async def test_send_magic_link_error(
    mock_send: AsyncMock,
) -> None:
    with pytest.raises(Exception, match="SMTP"):
        await send_magic_link(
            "user@example.com",
            "https://example.com?token=x",
        )
