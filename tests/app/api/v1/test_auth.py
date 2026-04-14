from unittest.mock import AsyncMock, patch

import pytest
from dotsound_private_core.contracts import (
    INTERNAL_SECRET_HEADER,
)
from httpx import AsyncClient

from tests.conftest import (
    create_test_user,
)

pytestmark = pytest.mark.anyio

_AUTH_GEN_CODE_PATH = "/api/v1/auth/" + "generate-code"


async def test_mock_auth_creates_user_and_returns_token(
    client: AsyncClient,
) -> None:
    r = await client.post("/api/v1/auth/mock/1")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user_id"] == 1
    assert data["token_type"] == "bearer"


async def test_mock_auth_returns_same_user_on_repeat(
    client: AsyncClient,
) -> None:
    r1 = await client.post("/api/v1/auth/mock/42")
    r2 = await client.post("/api/v1/auth/mock/42")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert (
        r1.json()["user_id"]
        == r2.json()["user_id"]
    )


async def test_telegram_auth_rejects_invalid_init_data(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": "garbage_data"},
    )
    assert r.status_code in (401, 503)


async def test_auth_config_returns_bot_username(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/auth/config")
    assert r.status_code == 200
    assert "bot_username" in r.json()


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_generate_code_no_secret(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    with patch(
        "app.api.v1.auth.settings"
    ) as s:
        s.bot_internal_secret = ""
        r = await client.post(
            _AUTH_GEN_CODE_PATH,
            json={"telegram_id": 100},
        )
    assert r.status_code == 503


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_generate_code_bad_secret(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    with patch(
        "app.api.v1.auth.settings"
    ) as s:
        s.bot_internal_secret = "correct"
        r = await client.post(
            _AUTH_GEN_CODE_PATH,
            json={"telegram_id": 100},
            headers={INTERNAL_SECRET_HEADER: "wrong"},
        )
    assert r.status_code == 403


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
@patch(
    "app.api.v1.auth.generate_code",
    return_value="ABC123",
)
async def test_generate_code_success(
    mock_gen: AsyncMock,
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    mock_redis.return_value = redis_mock

    with patch(
        "app.api.v1.auth.settings"
    ) as s:
        s.bot_internal_secret = "sec"
        r = await client.post(
            _AUTH_GEN_CODE_PATH,
            json={"telegram_id": 100},
            headers={
                INTERNAL_SECRET_HEADER: "sec"
            },
        )
    assert r.status_code == 200
    assert r.json()["code"] == "ABC123"


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
@patch(
    "app.api.v1.auth.generate_code",
    return_value="999999",
)
async def test_generate_code_blocked_by_cooldown(
    mock_gen: AsyncMock,
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=True
    )
    mock_redis.return_value = redis_mock

    with patch(
        "app.api.v1.auth.settings"
    ) as s:
        s.bot_internal_secret = "sec"
        r = await client.post(
            _AUTH_GEN_CODE_PATH,
            json={"telegram_id": 100},
            headers={
                INTERNAL_SECRET_HEADER: "sec"
            },
        )
    assert r.status_code == 429


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_verify_code_expired(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    mock_redis.return_value = redis_mock

    r = await client.post(
        "/api/v1/auth/verify-code",
        json={"code": "NOEXIST"},
    )
    assert r.status_code == 401


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_verify_code_user_not_found(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=b"999999"
    )
    redis_mock.delete = AsyncMock()
    mock_redis.return_value = redis_mock

    r = await client.post(
        "/api/v1/auth/verify-code",
        json={"code": "X123"},
    )
    assert r.status_code == 404


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_verify_code_success(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70001)

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=str(
            user["telegram_id"]
        ).encode()
    )
    redis_mock.delete = AsyncMock()
    mock_redis.return_value = redis_mock

    with patch(
        "app.api.v1.auth.httpx.AsyncClient"
    ) as mock_httpx:
        hc = AsyncMock()
        hc.post = AsyncMock()
        hc.__aenter__ = AsyncMock(
            return_value=hc
        )
        hc.__aexit__ = AsyncMock(
            return_value=False
        )
        mock_httpx.return_value = hc

        r = await client.post(
            "/api/v1/auth/verify-code",
            json={"code": "VALID"},
        )

    assert r.status_code == 200
    assert "access_token" in r.json()


@patch(
    "app.api.v1.auth._get_redis",
    new_callable=AsyncMock,
)
async def test_verify_code_strips_whitespace(
    mock_redis: AsyncMock,
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70002)

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=str(
            user["telegram_id"]
        ).encode()
    )
    redis_mock.delete = AsyncMock()
    mock_redis.return_value = redis_mock

    with patch(
        "app.api.v1.auth.httpx.AsyncClient"
    ) as mock_httpx:
        hc = AsyncMock()
        hc.post = AsyncMock()
        hc.__aenter__ = AsyncMock(
            return_value=hc
        )
        hc.__aexit__ = AsyncMock(
            return_value=False
        )
        mock_httpx.return_value = hc

        r = await client.post(
            "/api/v1/auth/verify-code",
            json={"code": "123 456"},
        )

    assert r.status_code == 200
    redis_mock.get.assert_awaited_once_with(
        "auth_code:123456"
    )


async def test_internal_token_forbidden_ip(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/auth/internal-token",
        json={"telegram_id": 100},
    )
    assert r.status_code in (403, 503)
