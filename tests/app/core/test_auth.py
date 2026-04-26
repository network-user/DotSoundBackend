from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from jose import jwt

from app.core.auth import (
    _ALGORITHM,
    AuthError,
    create_access_token,
    decode_access_token,
    verify_telegram_init_data,
)

pytestmark = pytest.mark.anyio

_JWT_SECRET = "test-secret-key-for-unit-tests"
_BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _patch_settings(**overrides: object):
    defaults = {
        "jwt_secret": _JWT_SECRET,
        "jwt_expire_days": 7,
        "telegram_bot_token": _BOT_TOKEN,
    }
    defaults.update(overrides)

    class _FakeSettings:
        pass

    obj = _FakeSettings()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return patch("app.core.auth.settings", obj)


def _build_init_data(
    user_dict: dict[str, object],
    bot_token: str = _BOT_TOKEN,
    auth_date: int | None = None,
    tamper_hash: bool = False,
) -> str:
    if auth_date is None:
        auth_date = int(time.time())
    user_json = json.dumps(user_dict)
    params = {
        "user": user_json,
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(
        sorted(f"{k}={v}" for k, v in params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if tamper_hash:
        computed_hash = "a" * 64
    parts = [f"{k}={v}" for k, v in params.items()]
    parts.append(f"hash={computed_hash}")
    return "&".join(parts)


class TestCreateAccessToken:
    async def test_creates_valid_jwt(self) -> None:
        with _patch_settings():
            token = create_access_token(42, False)

        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_ALGORITHM],
        )
        assert payload["sub"] == "42"
        assert payload["admin"] is False
        assert "exp" in payload

    async def test_admin_flag_propagated(self) -> None:
        with _patch_settings():
            token = create_access_token(1, True)

        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_ALGORITHM],
        )
        assert payload["admin"] is True

    async def test_expiration_set_correctly(
        self,
    ) -> None:
        with _patch_settings(jwt_expire_days=3):
            token = create_access_token(1, False)

        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_ALGORITHM],
        )
        exp_dt = datetime.fromtimestamp(
            payload["exp"], tz=UTC
        )
        expected_min = datetime.now(
            UTC
        ) + timedelta(days=2, hours=23)
        assert exp_dt > expected_min


class TestDecodeAccessToken:
    async def test_valid_token(self) -> None:
        with _patch_settings():
            token = create_access_token(99, True)
            payload = decode_access_token(token)

        assert payload["sub"] == "99"
        assert payload["admin"] is True

    @pytest.mark.parametrize(
        "token_factory",
        [
            pytest.param(
                lambda: jwt.encode(
                    {
                        "sub": "1",
                        "admin": False,
                        "exp": datetime.now(UTC)
                        - timedelta(hours=1),
                    },
                    _JWT_SECRET,
                    algorithm=_ALGORITHM,
                ),
                id="expired",
            ),
            pytest.param(
                lambda: "not.a.jwt",
                id="malformed",
            ),
            pytest.param(
                lambda: jwt.encode(
                    {
                        "sub": "1",
                        "admin": False,
                        "exp": datetime.now(
                            UTC
                        )
                        + timedelta(days=1),
                    },
                    "wrong-secret",
                    algorithm=_ALGORITHM,
                ),
                id="wrong_secret",
            ),
        ],
    )
    async def test_invalid_token_raises(
        self,
        token_factory: object,
    ) -> None:
        token = token_factory()
        with _patch_settings(), pytest.raises(
            AuthError
        ):
            decode_access_token(token)


class TestVerifyTelegramInitData:
    async def test_valid_init_data(self) -> None:
        user = {
            "id": 12345,
            "first_name": "Test",
            "username": "testuser",
        }
        init_data = _build_init_data(user)

        with _patch_settings():
            result = verify_telegram_init_data(
                init_data
            )

        assert result["id"] == 12345
        assert result["username"] == "testuser"

    async def test_invalid_hash_raises(self) -> None:
        user = {"id": 1, "first_name": "T"}
        init_data = _build_init_data(
            user, tamper_hash=True
        )

        with _patch_settings(), pytest.raises(AuthError):
            verify_telegram_init_data(init_data)

    async def test_missing_hash_raises(self) -> None:
        init_data = (
            "user=%7B%22id%22%3A1%7D&auth_date=123"
        )

        with _patch_settings(), pytest.raises(AuthError):
            verify_telegram_init_data(init_data)

    async def test_expired_auth_date_raises(
        self,
    ) -> None:
        user = {"id": 1, "first_name": "T"}
        old_ts = int(time.time()) - 90000
        init_data = _build_init_data(
            user, auth_date=old_ts
        )

        with _patch_settings(), pytest.raises(AuthError):
            verify_telegram_init_data(init_data)
