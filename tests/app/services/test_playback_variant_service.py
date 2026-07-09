import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.playback_variant_service import PlaybackVariantService

pytestmark = pytest.mark.anyio


async def _user(session: AsyncSession) -> User:
    u = User(telegram_id=88001, first_name="U")
    session.add(u)
    await session.flush()
    await session.refresh(u)
    return u


async def test_resolve_by_composition_group_id(
    db_session: AsyncSession,
) -> None:
    u = await _user(db_session)
    gid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    t1 = Track(
        title="A",
        artist="X",
        duration_seconds=100,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        composition_group_id=gid,
        source_platform="soundcloud",
    )
    t2 = Track(
        title="B",
        artist="Y",
        duration_seconds=200,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        composition_group_id=gid,
        source_platform="youtube",
    )
    db_session.add_all([t1, t2])
    await db_session.commit()
    await db_session.refresh(t1)
    await db_session.refresh(t2)

    svc = PlaybackVariantService(db_session)
    ids = await svc.resolve_variant_track_ids(t1)
    assert set(ids) == {t1.id, t2.id}


async def test_singleton_without_group(
    db_session: AsyncSession,
) -> None:
    u = await _user(db_session)
    t = Track(
        title="Solo",
        artist="Z",
        duration_seconds=50,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        source_platform="soundcloud",
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    svc = PlaybackVariantService(db_session)
    ids = await svc.resolve_variant_track_ids(t)
    assert ids == [t.id]


async def test_resolve_variant_track_ids_batch_matches_single(
    db_session: AsyncSession,
) -> None:
    u = await _user(db_session)
    gid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    t1 = Track(
        title="A",
        artist="X",
        duration_seconds=100,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        composition_group_id=gid,
        source_platform="soundcloud",
    )
    t2 = Track(
        title="B",
        artist="Y",
        duration_seconds=200,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        composition_group_id=gid,
        source_platform="youtube",
    )
    solo = Track(
        title="Solo",
        artist="Z",
        duration_seconds=50,
        is_active=True,
        is_public=True,
        uploaded_by_id=u.id,
        source_platform="soundcloud",
    )
    db_session.add_all([t1, t2, solo])
    await db_session.commit()
    for t in (t1, t2, solo):
        await db_session.refresh(t)

    svc = PlaybackVariantService(db_session)
    batch = await svc.resolve_variant_track_ids_batch([t1, t2, solo])

    # 1:1 parity with the single resolver, per track.
    assert batch[t1.id] == await svc.resolve_variant_track_ids(t1)
    assert batch[t2.id] == await svc.resolve_variant_track_ids(t2)
    assert batch[solo.id] == await svc.resolve_variant_track_ids(solo)
    assert set(batch[t1.id]) == {t1.id, t2.id}
    assert batch[solo.id] == [solo.id]
