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


@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
async def test_find_by_source_sha256_and_claim(
    _put: AsyncMock,
    db_session: AsyncSession,
) -> None:
    svc = AudioBlobService(db_session)
    b, _ = await svc.get_or_create_from_bytes(
        b"src1", "mp3", "audio/mpeg"
    )
    src = "1" * 64
    assert await svc.find_by_source_sha256(src) is None
    await svc.claim_source(blob=b, source_sha256=src)
    await db_session.flush()
    found = await svc.find_by_source_sha256(src)
    assert found is not None and found.id == b.id
    # Idempotent: second claim with a different value must not overwrite.
    await svc.claim_source(blob=b, source_sha256="2" * 64)
    await db_session.refresh(b)
    assert b.source_sha256 == src


@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
async def test_attach_pending_tracks_reconciles_after_transcode(
    _put: AsyncMock,
    db_session: AsyncSession,
) -> None:
    """User B re-uploads a source while user A's transcode is still
    running. User B's Track stays processing with source_sha256 set
    but no blob_id; once the transcode finishes for user A, the post
    hook attaches the blob to B as well."""
    u_a = User(telegram_id=5010, username="ua", first_name="A")
    u_b = User(telegram_id=5011, username="ub", first_name="B")
    db_session.add_all([u_a, u_b])
    await db_session.flush()
    await db_session.refresh(u_a)
    await db_session.refresh(u_b)

    src = "abc" + "0" * 61
    pending_b = Track(
        title="B",
        file_key=None,
        uploaded_by_id=u_b.id,
        is_active=True,
        processing_status="processing",
        source_sha256=src,
    )
    db_session.add(pending_b)
    await db_session.flush()

    svc = AudioBlobService(db_session)
    blob, _ = await svc.get_or_create_from_bytes(
        b"transcode-output", "mp3", "audio/mpeg"
    )
    await svc.claim_source(blob=blob, source_sha256=src)
    await svc.set_hls_manifest_key(
        blob=blob, hls_manifest_key="hls-blobs/ab/abc.../master.m3u8"
    )

    reconciled = await svc.attach_pending_tracks(
        source_sha256=src, blob=blob
    )
    assert reconciled == 1
    await db_session.refresh(pending_b)
    assert pending_b.blob_id == blob.id
    assert pending_b.file_key == blob.s3_key
    assert pending_b.processing_status == "active"
    assert (
        pending_b.hls_manifest_key
        == "hls-blobs/ab/abc.../master.m3u8"
    )


@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
async def test_two_users_active_on_same_blob_no_unique_violation(
    _put: AsyncMock,
    db_session: AsyncSession,
) -> None:
    """Phase A3: the partial unique index that used to prevent one user
    from having multiple active Tracks on the same blob has been dropped,
    and there has never been a constraint between different users."""
    u = User(telegram_id=5020, username="u", first_name="U")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    svc = AudioBlobService(db_session)
    b, _ = await svc.get_or_create_from_bytes(
        b"shared-bytes", "mp3", "audio/mpeg"
    )
    t1 = Track(
        title="One",
        file_key=None,
        uploaded_by_id=u.id,
        is_active=True,
    )
    t2 = Track(
        title="Two",
        file_key=None,
        uploaded_by_id=u.id,
        is_active=True,
    )
    db_session.add_all([t1, t2])
    await db_session.flush()
    await svc.attach_playback_blob(t1, b)
    await svc.attach_playback_blob(t2, b)
    await db_session.refresh(b)
    assert b.ref_count == 2
