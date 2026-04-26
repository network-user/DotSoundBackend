from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.email_auth_service import (
    EmailAuthError,
)
from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio

_MOD = "app.api.v1.auth_email"


async def test_email_request_returns_check_inbox(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.request_magic_link",
        new_callable=AsyncMock,
    ), patch(
        "app.core.tor_checker.is_tor_exit_node",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(f"{_MOD}.settings") as ms:
        ms.resend_api_key = "fake-key"
        r = await client.post(
            "/api/v1/auth/email/request",
            json={"email": "test@example.com"},
        )
    assert r.status_code == 200
    assert "inbox" in r.json()["message"].lower()


async def test_email_request_rejects_invalid_email(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/auth/email/request",
        json={"email": "not-an-email"},
    )
    assert r.status_code == 422


async def test_email_verify_rejects_bad_token(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_magic_link",
        new_callable=AsyncMock,
        side_effect=EmailAuthError(
            "Invalid token"
        ),
    ):
        r = await client.post(
            "/api/v1/auth/email/verify",
            json={"token": "bogus-token"},
        )
    assert r.status_code == 401


async def test_email_request_missing_body(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/auth/email/request",
        json={},
    )
    assert r.status_code == 422


async def test_email_verify_success_no_2fa(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_magic_link",
        new_callable=AsyncMock,
        return_value={
            "requires_2fa": False,
            "access_token": "tok",
            "user_id": 1,
            "is_admin": False,
        },
    ):
        r = await client.post(
            "/api/v1/auth/email/verify",
            json={"token": "valid-token"},
        )
    assert r.status_code == 200
    assert r.json()["access_token"] == "tok"


async def test_email_verify_requires_2fa(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_magic_link",
        new_callable=AsyncMock,
        return_value={
            "requires_2fa": True,
            "session_token": "sess_tok",
            "user_id": 1,
        },
    ):
        r = await client.post(
            "/api/v1/auth/email/verify",
            json={"token": "valid-token"},
        )
    assert r.status_code == 200
    assert r.json()["requires_2fa"] is True


async def test_2fa_verify_success(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_2fa",
        new_callable=AsyncMock,
        return_value={
            "access_token": "tok",
            "user_id": 1,
            "is_admin": False,
        },
    ):
        r = await client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "session_token": "st",
                "code": "123456",
            },
        )
    assert r.status_code == 200
    assert r.json()["access_token"] == "tok"


async def test_2fa_verify_invalid(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_2fa",
        new_callable=AsyncMock,
        side_effect=EmailAuthError("Invalid"),
    ):
        r = await client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "session_token": "st",
                "code": "000",
            },
        )
    assert r.status_code == 401


async def test_2fa_setup(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80001)
    headers = await auth_headers(
        client, user["id"]
    )

    with patch(
        f"{_MOD}.setup_2fa",
        new_callable=AsyncMock,
        return_value={
            "otpauth_uri": "otpauth://",
            "qr_code_base64": "qr",
            "backup_codes": ["A", "B"],
            "secret": "SEC",
        },
    ):
        r = await client.post(
            "/api/v1/auth/2fa/setup",
            headers=headers,
        )
    assert r.status_code == 200
    assert "qr_code_base64" in r.json()


async def test_2fa_setup_already_enabled(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80002)
    headers = await auth_headers(
        client, user["id"]
    )

    with patch(
        f"{_MOD}.setup_2fa",
        new_callable=AsyncMock,
        side_effect=EmailAuthError("already"),
    ):
        r = await client.post(
            "/api/v1/auth/2fa/setup",
            headers=headers,
        )
    assert r.status_code == 400


async def test_2fa_confirm(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80003)
    headers = await auth_headers(
        client, user["id"]
    )

    with patch(
        f"{_MOD}.confirm_2fa",
        new_callable=AsyncMock,
    ):
        r = await client.post(
            "/api/v1/auth/2fa/confirm",
            headers=headers,
            json={"code": "123456"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "2fa_enabled"


async def test_2fa_confirm_bad_code(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80004)
    headers = await auth_headers(
        client, user["id"]
    )

    with patch(
        f"{_MOD}.confirm_2fa",
        new_callable=AsyncMock,
        side_effect=EmailAuthError("Invalid"),
    ):
        r = await client.post(
            "/api/v1/auth/2fa/confirm",
            headers=headers,
            json={"code": "000000"},
        )
    assert r.status_code == 400


async def test_2fa_disable(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80005)
    headers = await auth_headers(
        client, user["id"]
    )

    with patch(
        f"{_MOD}.disable_2fa",
        new_callable=AsyncMock,
    ):
        r = await client.request(
            "DELETE",
            "/api/v1/auth/2fa",
            headers=headers,
            json={"code": "123456"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "2fa_disabled"


async def test_2fa_email_fallback(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.send_2fa_fallback",
        new_callable=AsyncMock,
    ):
        r = await client.post(
            "/api/v1/auth/2fa/email-fallback",
            json={"session_token": "st"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "code_sent"


async def test_2fa_email_fallback_error(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.send_2fa_fallback",
        new_callable=AsyncMock,
        side_effect=EmailAuthError("wait"),
    ):
        r = await client.post(
            "/api/v1/auth/2fa/email-fallback",
            json={"session_token": "st"},
        )
    assert r.status_code == 400


async def test_2fa_email_fallback_verify_success(
    client: AsyncClient,
) -> None:
    with patch(
        f"{_MOD}.verify_2fa_email_code",
        new_callable=AsyncMock,
        return_value={
            "access_token": "tok",
            "user_id": 1,
            "is_admin": False,
        },
    ):
        r = await client.post(
            "/api/v1/auth/2fa/email-fallback"
            "/verify",
            json={
                "session_token": "st",
                "code": "123456",
            },
        )
    assert r.status_code == 200
    assert r.json()["access_token"] == "tok"


async def test_2fa_email_fallback_verify_no_code(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/auth/2fa/email-fallback/verify",
        json={"session_token": "st"},
    )
    assert r.status_code == 400


async def test_email_request_not_configured(
    client: AsyncClient,
) -> None:
    with patch(f"{_MOD}.settings") as ms:
        ms.resend_api_key = ""
        r = await client.post(
            "/api/v1/auth/email/request",
            json={"email": "a@b.com"},
        )
    assert r.status_code == 503
