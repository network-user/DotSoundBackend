from __future__ import annotations

import base64
import json
from unittest.mock import patch

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.admin_capability import (
    AdminCapabilityRepository,
)
from app.services import admin_auth_service
from app.services.admin_auth_service import (
    AdminAuthError,
    confirm_admin_init,
    consume_backup_code,
    consume_step_up,
    is_locked_out,
    metadata_summary,
    regenerate_backup_codes,
    release_lockout,
    rotate_admin_refresh,
    start_admin_init,
    verify_admin_login,
    verify_step_up,
)
from app.services.admin_manifest_service import KNOWN_CAPABILITIES

pytestmark = pytest.mark.anyio


_FERNET_KEY = base64.urlsafe_b64encode(
    b"0" * 32
).decode()


def _patch_totp_settings():
    class _Cfg:
        totp_encryption_key = _FERNET_KEY

    return patch(
        "app.core.totp.settings", _Cfg()
    )


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, tuple[str, int]] = {}

    async def setex(
        self, key: str, ttl: int, value: str
    ) -> None:
        self.store[key] = (value, ttl)

    async def get(
        self, key: str
    ) -> bytes | None:
        if key not in self.store:
            return None
        return self.store[key][0].encode()

    async def delete(self, key: str) -> int:
        existed = 1 if key in self.store else 0
        self.store.pop(key, None)
        return existed

    async def keys(self, pattern: str):
        return [
            k
            for k in self.store
            if pattern.replace("*", "") in k
        ]

    async def ttl(self, key: str) -> int:
        if key not in self.store:
            return -2
        return self.store[key][1]


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()
    monkeypatch.setattr(
        admin_auth_service,
        "get_redis_client",
        lambda: fake,
    )
    monkeypatch.setattr(
        "app.services.admin_device_service.get_redis_client",
        lambda: fake,
    )
    return fake


async def _make_admin(
    db_session: AsyncSession,
    *,
    telegram_id: int,
    email: str | None = None,
) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name="Admin",
        is_admin=True,
        email=email,
        email_verified=email is not None,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_start_admin_init_returns_secret(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user = await _make_admin(
        db_session, telegram_id=300001
    )
    data = await start_admin_init(user)
    assert "secret_b32" in data
    assert "otpauth_uri" in data
    assert int(data["ttl_seconds"]) > 0  # type: ignore[arg-type]
    assert (
        f"admin:init:{user.id}" in fake_redis.store
    )


async def test_start_admin_init_rejects_non_admin(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user = User(
        telegram_id=300002,
        first_name="x",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()
    with pytest.raises(AdminAuthError):
        await start_admin_init(user)


async def test_confirm_admin_init_happy_path(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300003
        )
        data = await start_admin_init(user)
        secret = str(data["secret_b32"])
        code = pyotp.TOTP(secret).now()
        result = await confirm_admin_init(
            user=user,
            code=code,
            fingerprint="fp_init_1",
            label="laptop",
            ip="127.0.0.1",
            ua="ua",
            session=db_session,
        )
        assert (
            len(result["backup_codes"]) == 10  # type: ignore[arg-type]
        )
        assert user.admin_init is True
        assert user.admin_totp_enabled is True
        assert (
            user.admin_totp_secret_encrypted
            is not None
        )
        cap_repo = AdminCapabilityRepository(db_session)
        caps = await cap_repo.list_for_user(user.id)
        assert len(caps) == len(KNOWN_CAPABILITIES)


async def test_confirm_admin_init_wrong_code(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300004
        )
        await start_admin_init(user)
        with pytest.raises(AdminAuthError):
            await confirm_admin_init(
                user=user,
                code="000000",
                fingerprint="fp_init_2",
                label=None,
                ip=None,
                ua=None,
                session=db_session,
            )
        assert user.admin_init is False


async def test_verify_admin_login_unknown_device_pending(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session,
            telegram_id=300005,
            email="a@b.test",
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_known",
            label="known",
            ip=None,
            ua=None,
            session=db_session,
        )
        result = await verify_admin_login(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_unknown",
            ip=None,
            ua=None,
            session=db_session,
        )
        assert (
            result["requires_device_approval"]
            is True
        )


async def test_verify_admin_login_lockout_after_failures(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300006
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_lock",
            label=None,
            ip=None,
            ua=None,
            session=db_session,
        )
        for _ in range(5):
            with pytest.raises(AdminAuthError):
                await verify_admin_login(
                    user=user,
                    code="000000",
                    fingerprint="fp_lock",
                    ip="127.0.0.1",
                    ua=None,
                    session=db_session,
                )
        assert (
            await is_locked_out(user.id) is True
        )
        with pytest.raises(AdminAuthError):
            await verify_admin_login(
                user=user,
                code=pyotp.TOTP(secret).now(),
                fingerprint="fp_lock",
                ip="127.0.0.1",
                ua=None,
                session=db_session,
            )
        assert await release_lockout(user.id)
        assert (
            await is_locked_out(user.id) is False
        )


async def test_verify_step_up_marks_redis(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300007
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_step",
            label=None,
            ip=None,
            ua=None,
            session=db_session,
        )
        ok = await verify_step_up(
            user=user,
            code=pyotp.TOTP(secret).now(),
            action="users.ban",
        )
        assert ok is True
        assert (
            await consume_step_up(
                user_id=user.id,
                action="users.ban",
            )
            is True
        )
        assert (
            await consume_step_up(
                user_id=user.id,
                action="other.action",
            )
            is False
        )


async def test_rotate_admin_refresh_rejects_revoked(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300008
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        result = await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_refresh",
            label=None,
            ip=None,
            ua=None,
            session=db_session,
        )
        session_payload = result["session"]
        assert isinstance(session_payload, dict)
        old_refresh = str(
            session_payload["refresh_token"]
        )

        rotated = await rotate_admin_refresh(
            refresh_token=old_refresh,
            ip=None,
            ua=None,
            session=db_session,
        )
        assert "access_token" in rotated

        with pytest.raises(AdminAuthError):
            await rotate_admin_refresh(
                refresh_token=old_refresh,
                ip=None,
                ua=None,
                session=db_session,
            )


async def test_consume_backup_code_uses_each_once(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300009
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        result = await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_codes",
            label=None,
            ip=None,
            ua=None,
            session=db_session,
        )
        codes = list(result["backup_codes"])  # type: ignore[arg-type]
        first = codes[0]
        assert (
            consume_backup_code(user, first)
            is True
        )
        assert (
            consume_backup_code(user, first)
            is False
        )


async def test_regenerate_backup_codes(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    with _patch_totp_settings():
        user = await _make_admin(
            db_session, telegram_id=300010
        )
        init = await start_admin_init(user)
        secret = str(init["secret_b32"])
        await confirm_admin_init(
            user=user,
            code=pyotp.TOTP(secret).now(),
            fingerprint="fp_regen",
            label=None,
            ip=None,
            ua=None,
            session=db_session,
        )
        codes = await regenerate_backup_codes(
            user=user, session=db_session
        )
        assert len(codes) == 10
        stored = json.loads(
            user.admin_backup_codes_hash or "[]"
        )
        assert len(stored) == 10


async def test_metadata_summary_shape(
    db_session: AsyncSession,
) -> None:
    user = await _make_admin(
        db_session, telegram_id=300011
    )
    summary = metadata_summary(user=user)
    assert set(summary.keys()) == {
        "is_admin",
        "admin_init",
        "admin_totp_enabled",
        "has_backup_codes",
    }
