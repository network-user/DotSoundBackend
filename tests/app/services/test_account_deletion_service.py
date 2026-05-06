from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from dotsound_private_core.services.account_deletion_policy import (
    GRACE_PERIOD_DAYS,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.services.account_deletion_service import (
    AccountDeletionService,
)

pytestmark = pytest.mark.anyio


async def _make_user_with_deleted_at(
    session: AsyncSession,
    *,
    telegram_id: int,
    deleted_at: datetime | None,
    avatar_key: str | None = None,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, f"u{telegram_id}", "Bob", None
    )
    user.deleted_at = deleted_at
    user.avatar_key = avatar_key
    await session.flush()
    return user.id


async def test_hard_delete_skips_users_within_grace_period(
    session: AsyncSession,
) -> None:
    recent = datetime.now(UTC) - timedelta(days=5)
    uid = await _make_user_with_deleted_at(
        session, telegram_id=900, deleted_at=recent
    )

    svc = AccountDeletionService(session)
    summary = await svc.hard_delete_expired_users()

    assert summary["deleted"] == 0
    assert summary["scanned"] == 0
    repo = UserRepository(session)
    assert await repo.get_by_id(uid) is not None


async def test_hard_delete_removes_users_past_grace_period(
    session: AsyncSession,
) -> None:
    expired = datetime.now(UTC) - timedelta(
        days=GRACE_PERIOD_DAYS + 1
    )
    uid = await _make_user_with_deleted_at(
        session, telegram_id=901, deleted_at=expired
    )

    with patch(
        "app.services.account_deletion_service.s3.delete_object",
        new=AsyncMock(),
    ):
        svc = AccountDeletionService(session)
        summary = await svc.hard_delete_expired_users()

    assert summary["deleted"] == 1
    assert summary["scanned"] == 1
    assert summary["skipped"] == 0
    repo = UserRepository(session)
    assert await repo.get_by_id(uid) is None


async def test_hard_delete_drops_avatar_from_s3(
    session: AsyncSession,
) -> None:
    expired = datetime.now(UTC) - timedelta(
        days=GRACE_PERIOD_DAYS + 2
    )
    await _make_user_with_deleted_at(
        session,
        telegram_id=902,
        deleted_at=expired,
        avatar_key="avatars/abc.png",
    )

    delete_mock = AsyncMock()
    with patch(
        "app.services.account_deletion_service.s3.delete_object",
        new=delete_mock,
    ):
        svc = AccountDeletionService(session)
        summary = await svc.hard_delete_expired_users()

    assert summary["avatar_keys_freed"] == 1
    delete_mock.assert_awaited_once_with("avatars/abc.png")


async def test_hard_delete_skips_users_without_deleted_at(
    session: AsyncSession,
) -> None:
    await _make_user_with_deleted_at(
        session, telegram_id=903, deleted_at=None
    )

    svc = AccountDeletionService(session)
    summary = await svc.hard_delete_expired_users()

    assert summary["scanned"] == 0
    assert summary["deleted"] == 0


async def test_hard_delete_avatar_failure_does_not_block_deletion(
    session: AsyncSession,
) -> None:
    expired = datetime.now(UTC) - timedelta(
        days=GRACE_PERIOD_DAYS + 1
    )
    uid = await _make_user_with_deleted_at(
        session,
        telegram_id=904,
        deleted_at=expired,
        avatar_key="avatars/broken.png",
    )

    delete_mock = AsyncMock(side_effect=RuntimeError("s3 down"))
    with patch(
        "app.services.account_deletion_service.s3.delete_object",
        new=delete_mock,
    ):
        svc = AccountDeletionService(session)
        summary = await svc.hard_delete_expired_users()

    assert summary["deleted"] == 1
    assert summary["avatar_keys_freed"] == 0
    repo = UserRepository(session)
    assert await repo.get_by_id(uid) is None


async def test_hard_delete_batch_limit(
    session: AsyncSession,
) -> None:
    expired = datetime.now(UTC) - timedelta(
        days=GRACE_PERIOD_DAYS + 5
    )
    for tg in range(910, 915):
        await _make_user_with_deleted_at(
            session, telegram_id=tg, deleted_at=expired
        )

    with patch(
        "app.services.account_deletion_service.s3.delete_object",
        new=AsyncMock(),
    ):
        svc = AccountDeletionService(session)
        summary = await svc.hard_delete_expired_users(
            batch_limit=2
        )

    assert summary["scanned"] == 2
    assert summary["deleted"] == 2
