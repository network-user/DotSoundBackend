from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.promotion import PromotionRepository

pytestmark = pytest.mark.anyio


async def _seed_promotion(
    session: AsyncSession,
    *,
    entity_type: str = "track",
    entity_id: int = 1,
    surfaces: list[str] | None = None,
    priority: int = 0,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    is_active: bool = True,
):
    repo = PromotionRepository(session)
    return await repo.create(
        entity_type=entity_type,
        entity_id=entity_id,
        surfaces=surfaces if surfaces is not None else ["hero"],
        priority=priority,
        starts_at=starts_at,
        ends_at=ends_at,
        is_active=is_active,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        created_by_id=None,
    )


async def test_create_and_get(session: AsyncSession) -> None:
    promo = await _seed_promotion(session, entity_id=42)
    repo = PromotionRepository(session)
    found = await repo.get_by_id(promo.id)
    assert found is not None
    assert found.entity_type == "track"
    assert found.entity_id == 42
    assert found.surfaces == ["hero"]


async def test_list_for_admin_pagination_and_filter(
    session: AsyncSession,
) -> None:
    for i in range(5):
        await _seed_promotion(
            session,
            entity_type="track",
            entity_id=i + 1,
            surfaces=["hero"],
            priority=i,
        )
    await _seed_promotion(
        session,
        entity_type="artist",
        entity_id=100,
        surfaces=["section"],
    )
    repo = PromotionRepository(session)

    rows, total = await repo.list_for_admin(page=1, size=10)
    assert total == 6
    assert [r.entity_id for r in rows[:5]] == [5, 4, 3, 2, 1]

    rows, total = await repo.list_for_admin(
        page=1, size=10, entity_type="artist"
    )
    assert total == 1
    assert rows[0].entity_id == 100

    rows, _ = await repo.list_for_admin(
        page=1, size=10, surface="section"
    )
    assert all("section" in r.surfaces for r in rows)


async def test_list_active_for_surface_window(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    await _seed_promotion(
        session,
        entity_id=1,
        surfaces=["hero"],
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
    )
    await _seed_promotion(
        session,
        entity_id=2,
        surfaces=["hero"],
        starts_at=now + timedelta(hours=2),
    )
    await _seed_promotion(
        session,
        entity_id=3,
        surfaces=["hero"],
        ends_at=now - timedelta(hours=1),
    )
    await _seed_promotion(
        session,
        entity_id=4,
        surfaces=["hero"],
        is_active=False,
    )
    await _seed_promotion(
        session,
        entity_id=5,
        surfaces=["section"],
    )
    repo = PromotionRepository(session)
    rows = await repo.list_active_for_surface("hero", now)
    ids = {r.entity_id for r in rows}
    assert ids == {1}


async def test_list_active_priority_order(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    await _seed_promotion(session, entity_id=1, priority=10)
    await _seed_promotion(session, entity_id=2, priority=100)
    await _seed_promotion(session, entity_id=3, priority=50)
    repo = PromotionRepository(session)
    rows = await repo.list_active_for_surface("hero", now)
    assert [r.entity_id for r in rows] == [2, 3, 1]


async def test_update_partial(session: AsyncSession) -> None:
    promo = await _seed_promotion(session, entity_id=1, priority=0)
    repo = PromotionRepository(session)
    await repo.update(
        promo,
        priority=42,
        is_active=False,
    )
    updated = await repo.get_by_id(promo.id)
    assert updated is not None
    assert updated.priority == 42
    assert updated.is_active is False


async def test_record_and_aggregate_events(
    session: AsyncSession,
) -> None:
    promo = await _seed_promotion(session)
    repo = PromotionRepository(session)
    for _ in range(3):
        await repo.record_event(
            promotion_id=promo.id,
            event_type="impression",
            surface="hero",
            user_id=None,
        )
    await repo.record_event(
        promotion_id=promo.id,
        event_type="click",
        surface="hero",
        user_id=None,
    )
    counts = await repo.aggregate_event_counts(promo.id)
    assert counts["impression"] == 3
    assert counts["click"] == 1


async def test_delete_cascades_events(session: AsyncSession) -> None:
    promo = await _seed_promotion(session)
    repo = PromotionRepository(session)
    await repo.record_event(
        promotion_id=promo.id,
        event_type="impression",
        surface=None,
        user_id=None,
    )
    await repo.delete(promo)
    assert await repo.get_by_id(promo.id) is None
