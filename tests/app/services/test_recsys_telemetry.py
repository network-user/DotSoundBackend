import pytest
from dotsound_private_core.services.recommendation_engine import (
    get_algorithm_version,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation_impression import (
    RecommendationImpression,
)
from app.models.track import Track
from app.models.user import User
from app.services.recsys_telemetry import (
    RecsysTelemetryService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession, telegram_id: int
) -> User:
    user = User(telegram_id=telegram_id, first_name="U")
    session.add(user)
    await session.flush()
    return user


async def _make_track(
    session: AsyncSession, title: str = "T"
) -> Track:
    track = Track(title=title, file_key="k")
    session.add(track)
    await session.flush()
    return track


async def test_empty_track_ids_returns_empty_id(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 100)
    svc = RecsysTelemetryService(session)
    rec_id = await svc.record_impressions(
        user_id=user.id,
        surface="daily_mix",
        track_ids=[],
    )
    assert rec_id == ""


async def test_record_impressions_creates_rows(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 101)
    t1 = await _make_track(session, "t1")
    t2 = await _make_track(session, "t2")

    svc = RecsysTelemetryService(session)
    rec_id = await svc.record_impressions(
        user_id=user.id,
        surface="radio",
        track_ids=[t1.id, t2.id],
    )

    assert len(rec_id) == 32
    rows = (
        await session.execute(
            select(RecommendationImpression)
            .where(
                RecommendationImpression.recommendation_id
                == rec_id
            )
            .order_by(
                RecommendationImpression.position
            )
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[0].track_id == t1.id
    assert rows[0].position == 0
    assert rows[0].surface == "radio"
    assert (
        rows[0].algorithm_version
        == get_algorithm_version()
    )
    assert rows[1].track_id == t2.id
    assert rows[1].position == 1


async def test_each_call_unique_recommendation_id(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 102)
    t = await _make_track(session)

    svc = RecsysTelemetryService(session)
    rec1 = await svc.record_impressions(
        user_id=user.id,
        surface="daily_mix",
        track_ids=[t.id],
    )
    rec2 = await svc.record_impressions(
        user_id=user.id,
        surface="daily_mix",
        track_ids=[t.id],
    )
    assert rec1 != rec2


async def test_explicit_algorithm_version_override(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 103)
    t = await _make_track(session)

    svc = RecsysTelemetryService(session)
    rec_id = await svc.record_impressions(
        user_id=user.id,
        surface="for_you",
        track_ids=[t.id],
        algorithm_version="custom-v1",
    )
    row = (
        await session.execute(
            select(RecommendationImpression).where(
                RecommendationImpression.recommendation_id
                == rec_id
            )
        )
    ).scalar_one()
    assert row.algorithm_version == "custom-v1"
