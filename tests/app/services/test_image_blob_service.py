from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_blob import ImageBlob
from app.models.track import Track
from app.models.user import User
from app.services.image_blob_service import ImageBlobService

pytestmark = pytest.mark.anyio

_MOD = "app.services.image_blob_service"


async def _put_cas_side(
    _data: bytes, sha: str, ext: str, _ct: str
) -> str:
    return f"image-blobs/{sha[:2]}/{sha}.{ext}"


async def _make_user(session: AsyncSession, tid: int = 8100) -> User:
    u = User(telegram_id=tid, first_name="U")
    session.add(u)
    await session.flush()
    await session.refresh(u)
    return u


async def _make_track(session: AsyncSession, user: User) -> Track:
    t = Track(title="T", is_active=True, uploaded_by_id=user.id)
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_side)
async def test_dedup_same_bytes(
    _put: AsyncMock, db_session: AsyncSession
) -> None:
    svc = ImageBlobService(db_session)
    b1, c1 = await svc.get_or_create_from_bytes(b"img", "webp", "image/webp")
    b2, c2 = await svc.get_or_create_from_bytes(b"img", "webp", "image/webp")
    assert c1 is True
    assert c2 is False
    assert b1.id == b2.id
    _put.assert_awaited_once()


@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_side)
async def test_different_bytes_create_separate_blobs(
    _put: AsyncMock, db_session: AsyncSession
) -> None:
    svc = ImageBlobService(db_session)
    b1, _ = await svc.get_or_create_from_bytes(b"img_a", "webp", "image/webp")
    b2, _ = await svc.get_or_create_from_bytes(b"img_b", "webp", "image/webp")
    assert b1.id != b2.id


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_side)
async def test_try_release_deletes_s3_when_last_ref(
    _put: AsyncMock,
    mock_del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = await _make_track(db_session, user)
    svc = ImageBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"cover", "webp", "image/webp")
    track.cover_blob_id = blob.id
    await svc.attach(blob)
    await db_session.flush()
    await db_session.refresh(blob)
    assert blob.ref_count == 1

    await svc.try_release_for_track(track)
    await db_session.commit()

    gone = await db_session.get(ImageBlob, blob.id)
    assert gone is None
    mock_del.assert_awaited()


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_side)
async def test_try_release_for_track_idempotent(
    _put: AsyncMock,
    mock_del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    """Second call must be a no-op — ref_count does not go negative."""
    user = await _make_user(db_session, tid=8101)
    track = await _make_track(db_session, user)
    svc = ImageBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"cover2", "webp", "image/webp")
    track.cover_blob_id = blob.id
    await svc.attach(blob)
    await db_session.flush()
    await db_session.commit()

    t2 = await db_session.get(Track, track.id)
    assert t2 is not None

    await svc.try_release_for_track(t2)
    await db_session.commit()

    t3 = await db_session.get(Track, track.id)
    assert t3 is not None
    assert t3.cover_blob_ref_freed is True

    await svc.try_release_for_track(t3)
    await db_session.commit()

    assert mock_del.await_count == 1


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_side)
async def test_two_tracks_share_blob_ref_count(
    _put: AsyncMock,
    mock_del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, tid=8102)
    t1 = await _make_track(db_session, user)
    t2 = await _make_track(db_session, user)
    svc = ImageBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"shared", "webp", "image/webp")
    t1.cover_blob_id = blob.id
    t2.cover_blob_id = blob.id
    await svc.attach(blob)
    await svc.attach(blob)
    await db_session.flush()
    await db_session.refresh(blob)
    assert blob.ref_count == 2

    await svc.try_release_for_track(t1)
    await db_session.commit()

    b_mid = await db_session.get(ImageBlob, blob.id)
    assert b_mid is not None
    assert b_mid.ref_count == 1
    mock_del.assert_not_awaited()

    await db_session.refresh(t2)
    await svc.try_release_for_track(t2)
    await db_session.commit()

    b_gone = await db_session.get(ImageBlob, blob.id)
    assert b_gone is None
    mock_del.assert_awaited()
