from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.models.user import User
from app.services.audio_blob_service import AudioBlobService

pytestmark = pytest.mark.anyio

_MOD = "app.services.audio_blob_service"


async def _put_cas_side(
    _data: bytes, sha: str, ext: str, _ct: str
) -> str:
    from app.core.s3 import build_cas_audio_key

    return build_cas_audio_key(sha, ext)


@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
async def test_get_or_create_dedupes_same_bytes(
    _mock: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=5000,
        username="u",
        first_name="T",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    svc = AudioBlobService(db_session)
    b1, c1 = await svc.get_or_create_from_bytes(
        b"same", "mp3", "audio/mpeg"
    )
    b2, c2 = await svc.get_or_create_from_bytes(
        b"same", "mp3", "audio/mpeg"
    )
    assert c1 is True
    assert c2 is False
    assert b1.id == b2.id


@patch("app.core.s3.delete_object", new_callable=AsyncMock)
@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
async def test_release_deletes_s3_when_last_ref(
    _put: AsyncMock,
    _del: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=5001,
        username="u2",
        first_name="T",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    svc = AudioBlobService(db_session)
    b, _ = await svc.get_or_create_from_bytes(
        b"one", "mp3", "audio/mpeg"
    )
    t = Track(
        title="x",
        file_key=None,
        uploaded_by_id=user.id,
        is_active=True,
    )
    db_session.add(t)
    await db_session.flush()
    await svc.attach_playback_blob(t, b)
    await db_session.refresh(b)
    assert b.ref_count == 1
    await db_session.commit()

    t2 = await db_session.get(Track, t.id)
    assert t2 is not None
    await svc.try_release_for_track(t2)
    await db_session.commit()
    b_after = await db_session.get(AudioBlob, b.id)
    assert b_after is None
    _del.assert_awaited()


@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
@patch("app.core.s3.delete_object", new_callable=AsyncMock)
async def test_two_users_reference_same_blob(
    mock_delete: AsyncMock,
    mock_put: AsyncMock,
    db_session: AsyncSession,
) -> None:
    u1 = User(
        telegram_id=5002,
        username="a",
        first_name="A",
    )
    u2 = User(
        telegram_id=5003,
        username="b",
        first_name="B",
    )
    db_session.add_all([u1, u2])
    await db_session.flush()
    await db_session.refresh(u1)
    await db_session.refresh(u2)
    svc = AudioBlobService(db_session)
    b, _ = await svc.get_or_create_from_bytes(
        b"shared", "mp3", "audio/mpeg"
    )
    t1 = Track(
        title="1",
        file_key=None,
        uploaded_by_id=u1.id,
        is_active=True,
    )
    t2 = Track(
        title="2",
        file_key=None,
        uploaded_by_id=u2.id,
        is_active=True,
    )
    db_session.add_all([t1, t2])
    await db_session.flush()
    await svc.attach_playback_blob(t1, b)
    await svc.attach_playback_blob(t2, b)
    await db_session.refresh(b)
    assert b.ref_count == 2
    await svc.try_release_for_track(t1)
    await db_session.commit()
    t1r = await db_session.get(Track, t1.id)
    b_r = await db_session.get(AudioBlob, b.id)
    assert t1r is not None
    assert b_r is not None
    assert b_r.ref_count == 1
    mock_delete.assert_not_awaited()
    await db_session.refresh(t2)
    await svc.try_release_for_track(t2)
    await db_session.commit()
    b_last = await db_session.get(AudioBlob, b.id)
    assert b_last is None
    mock_delete.assert_awaited()
