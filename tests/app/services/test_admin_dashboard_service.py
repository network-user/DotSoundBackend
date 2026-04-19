from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.services import admin_dashboard_service
from app.services.admin_dashboard_service import (
    collect_overview,
)

pytestmark = pytest.mark.anyio


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(
        self, key: str, ttl: int, value: str
    ) -> None:
        self.store[key] = value

    async def keys(self, pattern: str):
        return [
            k
            for k in self.store
            if pattern.replace("*", "") in k
        ]


@pytest.fixture
def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
):
    fake = FakeRedis()
    monkeypatch.setattr(
        admin_dashboard_service,
        "get_redis_client",
        lambda: fake,
    )
    return fake


async def test_collect_overview_aggregates_counts(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user = User(
        telegram_id=500001,
        first_name="x",
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    track = Track(
        title="t",
        artist="a",
        uploaded_by_id=user.id,
        is_active=True,
        is_public=True,
        source="internal",
        file_size_bytes=1024,
    )
    db_session.add(track)
    await db_session.flush()
    complaint = Complaint(
        track_id=track.id,
        reported_by_user_id=user.id,
        reason="r",
        reason_type="user",
        is_resolved=False,
    )
    db_session.add(complaint)
    await db_session.flush()
    overview = await collect_overview(
        db_session, use_cache=False
    )
    assert overview["users"]["total"] >= 1
    assert overview["tracks"]["total"] >= 1
    assert overview["complaints"]["open"] >= 1
    assert (
        "storage_bytes" in overview["tracks"]
    )


async def test_collect_overview_uses_cache(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    fake_redis.store[
        "admin:dashboard:overview"
    ] = (
        '{"generated_at": 1, '
        '"users": {"total": 7, "active": 7, '
        '"admins": 1, "new_24h": 0, '
        '"online_now": 0}, '
        '"tracks": {"total": 0, "active": 0, '
        '"new_24h": 0, "storage_bytes": 0}, '
        '"complaints": {"open": 0}, '
        '"jobs": {"active": 0, "failed_1h": 0}}'
    )
    overview = await collect_overview(db_session)
    assert overview["users"]["total"] == 7
