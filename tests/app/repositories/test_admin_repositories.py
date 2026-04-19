from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.admin_action_log import (
    AdminActionLogRepository,
)
from app.repositories.admin_device import (
    AdminDeviceRepository,
)
from app.repositories.admin_login_attempt import (
    AdminLoginAttemptRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.repositories.app_settings import (
    AppSettingsRepository,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    db_session: AsyncSession, *, telegram_id: int
) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name="Admin",
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_admin_action_log_write_and_query(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200001
    )
    repo = AdminActionLogRepository(db_session)
    await repo.write(
        user_id=user.id,
        action="users.ban",
        target_type="user",
        target_id="42",
        ip="127.0.0.1",
        meta={"reason": "spam"},
    )
    await repo.write(
        user_id=user.id,
        action="tracks.delete",
        target_type="track",
        target_id="100",
    )
    rows, total = await repo.list_paginated()
    assert total == 2
    assert {r.action for r in rows} == {
        "users.ban",
        "tracks.delete",
    }


async def test_admin_action_log_filters(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200002
    )
    repo = AdminActionLogRepository(db_session)
    await repo.write(
        user_id=user.id,
        action="users.ban",
        target_type="user",
    )
    await repo.write(
        user_id=user.id,
        action="users.unban",
        target_type="user",
    )
    rows, total = await repo.list_paginated(
        action="users.ban"
    )
    assert total == 1
    assert rows[0].action == "users.ban"


async def test_app_settings_feature_flag_round_trip(
    db_session: AsyncSession,
) -> None:
    repo = AppSettingsRepository(db_session)
    assert (
        await repo.get_feature_flag("dark_mode")
        is False
    )
    await repo.set_feature_flag(
        "dark_mode", True, updated_by=None
    )
    assert (
        await repo.get_feature_flag("dark_mode")
        is True
    )
    await repo.set_feature_flag(
        "dark_mode", False, updated_by=None
    )
    assert (
        await repo.get_feature_flag("dark_mode")
        is False
    )


async def test_app_settings_list_feature_flags(
    db_session: AsyncSession,
) -> None:
    repo = AppSettingsRepository(db_session)
    await repo.set_feature_flag(
        "a", True, updated_by=None
    )
    await repo.set_feature_flag(
        "b", False, updated_by=None
    )
    rows = await repo.list_feature_flags()
    keys = sorted(r.key for r in rows)
    assert keys == ["feature.a", "feature.b"]


async def test_admin_device_lifecycle(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200003
    )
    repo = AdminDeviceRepository(db_session)
    device = await repo.create_pending(
        user_id=user.id,
        fingerprint_hash="fp_abc",
        label="dev",
        ip="127.0.0.1",
        ua="ua",
    )
    assert device.trusted_at is None
    await repo.trust(device)
    assert device.trusted_at is not None
    await repo.touch(device, ip="127.0.0.2")
    assert device.last_seen_at is not None
    await repo.revoke(device)
    assert device.revoked_at is not None


async def test_admin_session_repo_create_and_revoke(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200004
    )
    devices = AdminDeviceRepository(db_session)
    device = await devices.create_pending(
        user_id=user.id,
        fingerprint_hash="fp_xyz",
        label="dev",
        ip=None,
        ua=None,
    )
    await devices.trust(device)
    sessions = AdminSessionRepository(db_session)
    session_row = await sessions.create(
        user_id=user.id,
        device_id=device.id,
        jti="jti1",
        refresh_jti="r1",
        ip=None,
        ua=None,
        ttl_seconds=900,
    )
    assert session_row.revoked_at is None
    found = await sessions.get_by_jti("jti1")
    assert found is not None
    await sessions.revoke(session_row)
    assert session_row.revoked_at is not None


async def test_admin_login_attempts_window(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200005
    )
    repo = AdminLoginAttemptRepository(
        db_session
    )
    for _ in range(3):
        await repo.record(
            user_id=user.id,
            ip="127.0.0.1",
            ua="ua",
            success=False,
            reason="bad_code",
        )
    failures = (
        await repo.count_failures_in_window(
            user_id=user.id,
            window_seconds=900,
        )
    )
    assert failures == 3


async def test_admin_action_log_export(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(
        db_session, telegram_id=200006
    )
    repo = AdminActionLogRepository(db_session)
    for i in range(5):
        await repo.write(
            user_id=user.id,
            action=f"act_{i}",
        )
    rows = await repo.stream_for_export()
    assert len(rows) == 5
    assert all(
        isinstance(r.created_at, datetime)
        for r in rows
    )
