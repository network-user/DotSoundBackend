from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.account_linking_service import (
    LinkingError,
    _create_link_email_token,
    request_link_email,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.account_linking_service"


async def _make_user(
    session: AsyncSession,
    telegram_id: int | None = 2300,
    email: str | None = None,
) -> User:
    uname = (
        f"u{telegram_id}" if telegram_id else None
    )
    user = User(
        telegram_id=telegram_id,
        username=uname,
        first_name="T",
        email=email,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def test_create_link_email_token() -> None:
    token = _create_link_email_token(
        1, "a@b.com"
    )

    assert isinstance(token, str)
    assert len(token) > 0


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.send_magic_link", new_callable=AsyncMock)
@patch(f"{_MOD}.is_disposable_email", return_value=False)
async def test_request_link_email_sends(
    mock_disp: AsyncMock,
    mock_send: AsyncMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    redis_mock = AsyncMock()
    mock_redis.return_value = redis_mock

    await request_link_email(
        user, "new@example.com"
    )

    mock_send.assert_awaited_once()


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.send_magic_link", new_callable=AsyncMock)
@patch(f"{_MOD}.is_disposable_email", return_value=True)
async def test_request_link_email_disposable(
    mock_disp: AsyncMock,
    mock_send: AsyncMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)

    with pytest.raises(
        LinkingError, match="Disposable"
    ):
        await request_link_email(
            user, "temp@trash.com"
        )


async def test_request_link_same_email(
    session: AsyncSession,
) -> None:
    user = await _make_user(
        session, email="same@example.com"
    )

    await request_link_email(
        user, "same@example.com"
    )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_email_expired(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        verify_link_email,
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    mock_redis.return_value = redis_mock

    user = await _make_user(session, 2301)
    token = _create_link_email_token(
        user.id, "a@b.com"
    )

    with pytest.raises(
        LinkingError, match="expired"
    ):
        await verify_link_email(token, session)


async def test_verify_link_email_bad_token(
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        verify_link_email,
    )

    with pytest.raises(LinkingError):
        await verify_link_email(
            "bad.token.value", session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_email_success(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    import json

    from app.services.account_linking_service import (
        verify_link_email,
    )

    user = await _make_user(session, 2310)
    token = _create_link_email_token(
        user.id, "new@example.com"
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=json.dumps(
            {
                "user_id": user.id,
                "email": "new@example.com",
            }
        ).encode()
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    result = await verify_link_email(
        token, session
    )

    assert result.email == "new@example.com"
    assert result.email_verified is True


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_email_user_not_found(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    import json

    from app.services.account_linking_service import (
        verify_link_email,
    )

    token = _create_link_email_token(
        99999, "x@y.com"
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=json.dumps(
            {
                "user_id": 99999,
                "email": "x@y.com",
            }
        ).encode()
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        LinkingError, match="User not found"
    ):
        await verify_link_email(token, session)


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_generate_link_telegram_code(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        generate_link_telegram_code,
    )

    user = await _make_user(session, 2320)

    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    code = await generate_link_telegram_code(user)

    assert isinstance(code, str)
    assert len(code) > 0


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_telegram_success(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        verify_link_telegram,
    )

    user = await _make_user(
        session, telegram_id=None, email="t@t.com"
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=str(user.id).encode()
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    result = await verify_link_telegram(
        "code123", 77777, session
    )

    assert result.telegram_id == 77777


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_telegram_expired(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        verify_link_telegram,
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        LinkingError, match="expired"
    ):
        await verify_link_telegram(
            "bad_code", 123, session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_link_telegram_user_not_found(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.account_linking_service import (
        verify_link_telegram,
    )

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=b"99999"
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        LinkingError, match="User not found"
    ):
        await verify_link_telegram(
            "code", 123, session
        )
