import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.email_auth_service import (
    EmailAuthError,
    _create_2fa_session_token,
    _create_magic_token,
    _decode_2fa_session_token,
    _decode_magic_token,
    _verify_backup_code,
    confirm_2fa,
    disable_2fa,
    setup_2fa,
    verify_2fa,
    verify_magic_link,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.email_auth_service"


def test_create_and_decode_magic_token() -> None:
    token = _create_magic_token("a@b.com")
    payload = _decode_magic_token(token)

    assert payload["sub"] == "a@b.com"
    assert payload["type"] == "magic_link"


def test_decode_invalid_token() -> None:
    with pytest.raises(EmailAuthError):
        _decode_magic_token("bad.token.value")


def test_decode_magic_token_wrong_type() -> None:
    token = _create_2fa_session_token(1)
    with pytest.raises(
        EmailAuthError, match="Invalid token type"
    ):
        _decode_magic_token(token)


def test_create_and_decode_2fa_session() -> None:
    token = _create_2fa_session_token(42)
    payload = _decode_2fa_session_token(token)

    assert payload["sub"] == "42"
    assert payload["type"] == "2fa_session"


def test_decode_2fa_session_invalid() -> None:
    with pytest.raises(EmailAuthError):
        _decode_2fa_session_token("bad.token")


def test_decode_2fa_session_wrong_type() -> None:
    token = _create_magic_token("a@b.com")
    with pytest.raises(
        EmailAuthError,
        match="Invalid session token type",
    ):
        _decode_2fa_session_token(token)


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.send_magic_link", new_callable=AsyncMock)
@patch(f"{_MOD}.is_disposable_email", return_value=False)
async def test_request_magic_link(
    mock_disp: AsyncMock,
    mock_send: AsyncMock,
    mock_redis: AsyncMock,
) -> None:
    from app.services.email_auth_service import (
        request_magic_link,
    )

    redis_mock = AsyncMock()
    mock_redis.return_value = redis_mock

    await request_magic_link("test@example.com")

    mock_send.assert_awaited_once()


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.send_magic_link", new_callable=AsyncMock)
@patch(f"{_MOD}.is_disposable_email", return_value=True)
async def test_request_magic_link_disposable(
    mock_disp: AsyncMock,
    mock_send: AsyncMock,
    mock_redis: AsyncMock,
) -> None:
    from app.services.email_auth_service import (
        request_magic_link,
    )

    await request_magic_link("test@tempmail.com")

    mock_send.assert_not_awaited()


async def test_setup_2fa_already_enabled() -> None:
    user = MagicMock()
    user.totp_enabled = True

    with pytest.raises(
        EmailAuthError, match="already"
    ):
        await setup_2fa(user)


@patch(f"{_MOD}.generate_qr_base64", return_value="qr")
@patch(f"{_MOD}.get_otpauth_uri", return_value="otpauth://")
@patch(f"{_MOD}.generate_totp_secret", return_value="SECRET")
@patch(f"{_MOD}.encrypt_secret", return_value="enc")
@patch(f"{_MOD}.generate_backup_codes", return_value=["CODE1"])
@patch(f"{_MOD}.hash_backup_code", return_value="hash1")
async def test_setup_2fa_success(
    mock_hash: MagicMock,
    mock_backup: MagicMock,
    mock_enc: MagicMock,
    mock_secret: MagicMock,
    mock_uri: MagicMock,
    mock_qr: MagicMock,
) -> None:
    user = MagicMock()
    user.totp_enabled = False
    user.id = 1
    user.email = "a@b.com"

    result = await setup_2fa(user)

    assert result["otpauth_uri"] == "otpauth://"
    assert result["qr_code_base64"] == "qr"
    assert result["backup_codes"] == ["CODE1"]
    assert result["secret"] == "SECRET"


@patch(f"{_MOD}.verify_totp", return_value=False)
@patch(f"{_MOD}.decrypt_secret", return_value="secret")
async def test_confirm_2fa_invalid_code(
    mock_decrypt: AsyncMock,
    mock_verify: AsyncMock,
) -> None:
    user = MagicMock()
    user.totp_enabled = False
    user.totp_secret_encrypted = "enc"

    with pytest.raises(
        EmailAuthError, match="Invalid TOTP"
    ):
        await confirm_2fa(user, "000000")


@patch(f"{_MOD}.verify_totp", return_value=True)
@patch(f"{_MOD}.decrypt_secret", return_value="secret")
async def test_confirm_2fa_success(
    mock_decrypt: MagicMock,
    mock_verify: MagicMock,
) -> None:
    user = MagicMock()
    user.totp_enabled = False
    user.totp_secret_encrypted = "enc"

    await confirm_2fa(user, "123456")

    assert user.totp_enabled is True


async def test_confirm_2fa_already_enabled() -> None:
    user = MagicMock()
    user.totp_enabled = True

    with pytest.raises(
        EmailAuthError, match="already enabled"
    ):
        await confirm_2fa(user, "123456")


async def test_confirm_2fa_no_secret() -> None:
    user = MagicMock()
    user.totp_enabled = False
    user.totp_secret_encrypted = None

    with pytest.raises(
        EmailAuthError, match="setup first"
    ):
        await confirm_2fa(user, "123456")


@patch(f"{_MOD}.verify_totp", return_value=True)
@patch(f"{_MOD}.decrypt_secret", return_value="secret")
async def test_disable_2fa_success(
    mock_decrypt: MagicMock,
    mock_verify: MagicMock,
) -> None:
    user = MagicMock()
    user.totp_enabled = True
    user.totp_secret_encrypted = "enc"

    await disable_2fa(user, "123456")

    assert user.totp_enabled is False
    assert user.totp_secret_encrypted is None
    assert user.backup_codes_hash is None


async def test_disable_2fa_not_enabled() -> None:
    user = MagicMock()
    user.totp_enabled = False

    with pytest.raises(
        EmailAuthError, match="not enabled"
    ):
        await disable_2fa(user, "123456")


async def test_disable_2fa_no_secret() -> None:
    user = MagicMock()
    user.totp_enabled = True
    user.totp_secret_encrypted = None

    with pytest.raises(
        EmailAuthError, match="not configured"
    ):
        await disable_2fa(user, "123456")


@patch(f"{_MOD}.verify_totp", return_value=False)
@patch(f"{_MOD}.decrypt_secret", return_value="secret")
async def test_disable_2fa_bad_code(
    mock_decrypt: MagicMock,
    mock_verify: MagicMock,
) -> None:
    user = MagicMock()
    user.totp_enabled = True
    user.totp_secret_encrypted = "enc"

    with pytest.raises(
        EmailAuthError, match="Invalid TOTP"
    ):
        await disable_2fa(user, "000000")


def test_verify_backup_code_valid() -> None:
    from app.core.totp import hash_backup_code

    code = "ABCDEF12"
    hashed = hash_backup_code(code)
    user = MagicMock()
    user.backup_codes_hash = json.dumps([hashed])

    result = _verify_backup_code(user, code)

    assert result is True
    remaining = json.loads(
        user.backup_codes_hash
    )
    assert hashed not in remaining


def test_verify_backup_code_invalid() -> None:
    user = MagicMock()
    user.backup_codes_hash = json.dumps(
        ["some_hash"]
    )

    result = _verify_backup_code(user, "WRONG")

    assert result is False


def test_verify_backup_code_none() -> None:
    user = MagicMock()
    user.backup_codes_hash = None

    result = _verify_backup_code(user, "X")

    assert result is False


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
@patch(f"{_MOD}.create_access_token", return_value="tok")
async def test_verify_magic_link_success(
    mock_token: MagicMock,
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    token = _create_magic_token("a@b.com")

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=b"a@b.com"
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.is_admin = False
    user_mock.totp_enabled = False

    svc = AsyncMock()
    svc.get_or_create_by_email = AsyncMock(
        return_value=(user_mock, False)
    )
    mock_svc_cls.return_value = svc

    result = await verify_magic_link(
        token, session
    )

    assert result["requires_2fa"] is False
    assert result["access_token"] == "tok"


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_verify_magic_link_expired(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    token = _create_magic_token("a@b.com")

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError, match="already used"
    ):
        await verify_magic_link(token, session)


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_verify_magic_link_inactive_user(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    token = _create_magic_token("a@b.com")

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=b"a@b.com"
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    user_mock = MagicMock()
    user_mock.is_active = False

    svc = AsyncMock()
    svc.get_or_create_by_email = AsyncMock(
        return_value=(user_mock, False)
    )
    mock_svc_cls.return_value = svc

    with pytest.raises(
        EmailAuthError, match="deactivated"
    ):
        await verify_magic_link(token, session)


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_verify_magic_link_requires_2fa(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    token = _create_magic_token("a@b.com")

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(
        return_value=b"a@b.com"
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.totp_enabled = True

    svc = AsyncMock()
    svc.get_or_create_by_email = AsyncMock(
        return_value=(user_mock, False)
    )
    mock_svc_cls.return_value = svc

    result = await verify_magic_link(
        token, session
    )

    assert result["requires_2fa"] is True
    assert "session_token" in result


@patch(f"{_MOD}.create_access_token", return_value="tok")
@patch(f"{_MOD}.verify_totp", return_value=True)
@patch(f"{_MOD}.decrypt_secret", return_value="s")
@patch(f"{_MOD}.UserService")
async def test_verify_2fa_with_totp(
    mock_svc_cls: MagicMock,
    mock_decrypt: MagicMock,
    mock_verify: MagicMock,
    mock_token: MagicMock,
    session: AsyncSession,
) -> None:
    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.is_admin = False
    user_mock.totp_enabled = True
    user_mock.totp_secret_encrypted = "enc"

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    result = await verify_2fa(
        session_token, "123456", None, session
    )

    assert result["access_token"] == "tok"


@patch(f"{_MOD}.UserService")
async def test_verify_2fa_user_not_found(
    mock_svc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    session_token = _create_2fa_session_token(99)

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(return_value=None)
    mock_svc_cls.return_value = svc

    with pytest.raises(
        EmailAuthError, match="User not found"
    ):
        await verify_2fa(
            session_token, "123", None, session
        )


@patch(f"{_MOD}.UserService")
async def test_verify_2fa_not_enabled(
    mock_svc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.totp_enabled = False

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    with pytest.raises(
        EmailAuthError, match="not enabled"
    ):
        await verify_2fa(
            session_token, "123", None, session
        )


@patch(f"{_MOD}.decrypt_secret", return_value="s")
@patch(f"{_MOD}.UserService")
async def test_verify_2fa_no_code_or_backup(
    mock_svc_cls: MagicMock,
    mock_decrypt: MagicMock,
    session: AsyncSession,
) -> None:
    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.totp_enabled = True
    user_mock.totp_secret_encrypted = "enc"

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    with pytest.raises(
        EmailAuthError,
        match="Provide code or backup_code",
    ):
        await verify_2fa(
            session_token, None, None, session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.send_totp_fallback_code", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_send_2fa_fallback_success(
    mock_svc_cls: MagicMock,
    mock_send: AsyncMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        send_2fa_fallback,
    )

    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.email = "a@b.com"

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        side_effect=[False, False]
    )
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    await send_2fa_fallback(session_token, session)

    mock_send.assert_awaited_once()


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_send_2fa_fallback_rate_limited(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        send_2fa_fallback,
    )

    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.email = "a@b.com"

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        side_effect=[False, True]
    )
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError, match="wait"
    ):
        await send_2fa_fallback(
            session_token, session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_send_2fa_fallback_no_email(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        send_2fa_fallback,
    )

    session_token = _create_2fa_session_token(1)

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(return_value=None)
    mock_svc_cls.return_value = svc

    with pytest.raises(
        EmailAuthError, match="not found"
    ):
        await send_2fa_fallback(
            session_token, session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.create_access_token", return_value="tok")
@patch(f"{_MOD}.UserService")
async def test_verify_2fa_email_code_success(
    mock_svc_cls: MagicMock,
    mock_token: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    redis_mock.get = AsyncMock(
        return_value=b"123456"
    )
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.is_active = True
    user_mock.is_admin = False

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    result = await verify_2fa_email_code(
        session_token, "123456", session
    )

    assert result["access_token"] == "tok"


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_2fa_email_code_expired(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError,
        match="Code expired or not found",
    ):
        await verify_2fa_email_code(
            session_token, "000000", session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_2fa_email_code_wrong(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    redis_mock.get = AsyncMock(
        return_value=b"123456"
    )
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError, match="Invalid code"
    ):
        await verify_2fa_email_code(
            session_token, "999999", session
        )

    redis_mock.incr.assert_awaited_once()


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_2fa_email_code_burned(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    redis_mock.get = AsyncMock(
        return_value=b"123456"
    )
    redis_mock.incr = AsyncMock(
        side_effect=[5, 1]
    )
    redis_mock.expire = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError,
        match="too many attempts",
    ):
        await verify_2fa_email_code(
            session_token, "999999", session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_2fa_email_code_cooldown(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=True
    )
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError,
        match="Too many failed attempts",
    ):
        await verify_2fa_email_code(
            session_token, "000000", session
        )


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
async def test_verify_2fa_email_burned_triggers_cooldown(
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        verify_2fa_email_code,
    )

    session_token = _create_2fa_session_token(1)

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=False
    )
    redis_mock.get = AsyncMock(
        return_value=b"123456"
    )
    redis_mock.incr = AsyncMock(
        side_effect=[5, 3]
    )
    redis_mock.expire = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError,
        match="too many attempts",
    ):
        await verify_2fa_email_code(
            session_token, "999999", session
        )

    redis_mock.setex.assert_awaited_once()


@patch(f"{_MOD}._get_redis", new_callable=AsyncMock)
@patch(f"{_MOD}.UserService")
async def test_send_2fa_fallback_blocked_by_cooldown(
    mock_svc_cls: MagicMock,
    mock_redis: AsyncMock,
    session: AsyncSession,
) -> None:
    from app.services.email_auth_service import (
        send_2fa_fallback,
    )

    session_token = _create_2fa_session_token(1)

    user_mock = MagicMock()
    user_mock.id = 1
    user_mock.email = "a@b.com"

    svc = AsyncMock()
    svc.get_by_id = AsyncMock(
        return_value=user_mock
    )
    mock_svc_cls.return_value = svc

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(
        return_value=True
    )
    redis_mock.aclose = AsyncMock()
    mock_redis.return_value = redis_mock

    with pytest.raises(
        EmailAuthError,
        match="Too many failed attempts",
    ):
        await send_2fa_fallback(
            session_token, session
        )
