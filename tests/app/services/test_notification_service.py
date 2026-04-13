from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.notification_service import (
    NotificationService,
)

pytestmark = pytest.mark.anyio

_WS = "app.core.ws_manager.ws_manager"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1300,
) -> int:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user.id


@patch(f"{_WS}.send_to_user", new_callable=AsyncMock)
async def test_create_notification(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = NotificationService(session)

    result = await svc.create(
        uid, "like", "New like", "Someone liked"
    )

    assert result["type"] == "like"
    assert result["title"] == "New like"
    mock_ws.assert_awaited_once()


@patch(f"{_WS}.send_to_user", new_callable=AsyncMock)
async def test_list_notifications(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = NotificationService(session)
    await svc.create(uid, "t", "T", "B")

    items = await svc.list_notifications(uid)

    assert len(items) == 1
    assert items[0]["title"] == "T"


@patch(f"{_WS}.send_to_user", new_callable=AsyncMock)
async def test_create_returns_event_fields(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = NotificationService(session)

    result = await svc.create(
        uid, "follow", "New follower", "X follows"
    )

    assert result["event"] == "notification"
    assert "id" in result
    assert "created_at" in result


@patch(f"{_WS}.send_to_user", new_callable=AsyncMock)
async def test_list_multiple_notifications(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = NotificationService(session)
    await svc.create(uid, "t", "T1", "B1")
    await svc.create(uid, "t", "T2", "B2")
    await svc.create(uid, "t", "T3", "B3")

    items = await svc.list_notifications(uid)

    assert len(items) == 3


@patch(f"{_WS}.send_to_user", new_callable=AsyncMock)
async def test_mark_read_changes_flag(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = NotificationService(session)
    result = await svc.create(uid, "t", "T", "B")

    await svc.mark_read(result["id"], uid)

    items = await svc.list_notifications(uid)
    assert items[0]["is_read"] is True
