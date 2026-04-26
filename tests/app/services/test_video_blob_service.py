from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.models.video_blob import VideoBlob
from app.services.video_blob_service import VideoBlobService

pytestmark = pytest.mark.anyio


async def _put_cas_video_side(
    _data: bytes, sha: str, ext: str, _ct: str
) -> str:
    return f"video-blobs/{sha[:2]}/{sha}.{ext}"


async def _put_cas_image_side(
    _data: bytes, sha: str, ext: str, _ct: str
) -> str:
    return f"image-blobs/{sha[:2]}/{sha}.{ext}"


async def _make_user(session: AsyncSession, tid: int = 8200) -> User:
    u = User(telegram_id=tid, first_name="V")
    session.add(u)
    await session.flush()
    await session.refresh(u)
    return u


async def _make_track(session: AsyncSession, user: User) -> Track:
    t = Track(title="VT", is_active=True, uploaded_by_id=user.id)
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


@patch("app.core.s3.put_cas_video", new_callable=AsyncMock, side_effect=_put_cas_video_side)
async def test_dedup_same_bytes(
    _put: AsyncMock, db_session: AsyncSession
) -> None:
    svc = VideoBlobService(db_session)
    b1, c1 = await svc.get_or_create_from_bytes(b"vid", "mp4", "video/mp4")
    b2, c2 = await svc.get_or_create_from_bytes(b"vid", "mp4", "video/mp4")
    assert c1 is True
    assert c2 is False
    assert b1.id == b2.id
    _put.assert_awaited_once()


@patch("app.core.s3.put_cas_video", new_callable=AsyncMock, side_effect=_put_cas_video_side)
async def test_attach_to_track_sets_fields(
    _put: AsyncMock, db_session: AsyncSession
) -> None:
    user = await _make_user(db_session)
    track = await _make_track(db_session, user)
    svc = VideoBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"video_a", "mp4", "video/mp4")
    await svc.attach_to_track(track, blob)
    await db_session.flush()
    await db_session.refresh(track)
    await db_session.refresh(blob)

    assert track.video_blob_id == blob.id
    assert track.video_key == blob.s3_key
    assert blob.ref_count == 1


@patch("app.core.s3.put_cas_image", new_callable=AsyncMock, side_effect=_put_cas_image_side)
@patch("app.core.s3.put_cas_video", new_callable=AsyncMock, side_effect=_put_cas_video_side)
async def test_set_thumbnail(
    _put_v: AsyncMock,
    _put_i: AsyncMock,
    db_session: AsyncSession,
) -> None:
    from app.services.image_blob_service import ImageBlobService

    vsvc = VideoBlobService(db_session)
    isvc = ImageBlobService(db_session)

    vblob, _ = await vsvc.get_or_create_from_bytes(b"video_b", "mp4", "video/mp4")
    iblob, _ = await isvc.get_or_create_from_bytes(b"thumb", "jpg", "image/jpeg")

    await vsvc.set_thumbnail(vblob, iblob)
    await db_session.flush()
    await db_session.refresh(vblob)

    assert vblob.thumbnail_blob_id == iblob.id


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch("app.core.s3.put_cas_video", new_callable=AsyncMock, side_effect=_put_cas_video_side)
async def test_try_release_deletes_when_last_ref(
    _put: AsyncMock,
    mock_del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, tid=8201)
    track = await _make_track(db_session, user)
    svc = VideoBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"vid_c", "mp4", "video/mp4")
    await svc.attach_to_track(track, blob)
    await db_session.flush()
    await db_session.commit()

    t2 = await db_session.get(Track, track.id)
    assert t2 is not None
    await svc.try_release_for_track(t2)
    await db_session.commit()

    gone = await db_session.get(VideoBlob, blob.id)
    assert gone is None
    mock_del.assert_awaited()


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch("app.core.s3.put_cas_video", new_callable=AsyncMock, side_effect=_put_cas_video_side)
async def test_try_release_for_track_idempotent(
    _put: AsyncMock,
    mock_del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, tid=8202)
    track = await _make_track(db_session, user)
    svc = VideoBlobService(db_session)

    blob, _ = await svc.get_or_create_from_bytes(b"vid_d", "mp4", "video/mp4")
    await svc.attach_to_track(track, blob)
    await db_session.flush()
    await db_session.commit()

    t2 = await db_session.get(Track, track.id)
    assert t2 is not None
    await svc.try_release_for_track(t2)
    await db_session.commit()

    t3 = await db_session.get(Track, track.id)
    assert t3 is not None
    assert t3.video_blob_ref_freed is True

    await svc.try_release_for_track(t3)
    await db_session.commit()

    assert mock_del.await_count == 1
