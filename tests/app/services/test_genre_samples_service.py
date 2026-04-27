from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.genre_sample import GenreSample
from app.models.track import Track
from app.models.user import User
from app.services.genre_samples_service import GenreSamplesService

pytestmark = pytest.mark.anyio


async def _user(session: AsyncSession, tid: int) -> User:
    u = User(
        telegram_id=tid,
        first_name="T",
    )
    session.add(u)
    await session.flush()
    return u


async def _blob(
    session: AsyncSession, bid: int, sha: str
) -> AudioBlob:
    b = AudioBlob(
        id=bid,
        content_sha256=sha,
        s3_key="k",
        content_type="audio/mpeg",
        size_bytes=100,
        ref_count=0,
    )
    session.add(b)
    await session.flush()
    return b


async def _track(
    session: AsyncSession,
    *,
    title: str,
    genre: str,
    play_count: int,
    uploader: User,
    blob: AudioBlob,
) -> Track:
    t = Track(
        title=title,
        genre=genre,
        duration_seconds=120,
        file_key="audio/k.mp3",
        blob_id=blob.id,
        is_active=True,
        is_public=True,
        play_count=play_count,
        uploaded_by_id=uploader.id,
    )
    session.add(t)
    await session.flush()
    return t


async def test_get_preview_queue_curated_then_backfill(
    session: AsyncSession,
) -> None:
    u = await _user(session, 90001)
    b1 = await _blob(session, 1, "a" * 64)
    b2 = await _blob(session, 2, "b" * 64)
    b3 = await _blob(session, 3, "c" * 64)
    t_popular = await _track(
        session,
        title="P",
        genre="Rock",
        play_count=100,
        uploader=u,
        blob=b1,
    )
    t_cur = await _track(
        session,
        title="C",
        genre="Rock",
        play_count=1,
        uploader=u,
        blob=b2,
    )
    other_genre = await _track(
        session,
        title="J",
        genre="Jazz",
        play_count=200,
        uploader=u,
        blob=b3,
    )
    session.add(
        GenreSample(
            genre="Rock",
            track_id=t_cur.id,
            position=0,
            curated=True,
        )
    )
    await session.flush()
    svc = GenreSamplesService(session)
    out = await svc.get_preview_queue("Rock", 5)
    assert [x.id for x in out] == [t_cur.id, t_popular.id]
    assert all(x.id != other_genre.id for x in out)


async def test_ensure_preview_clip_creates(
    session: AsyncSession,
) -> None:
    u = await _user(session, 90002)
    b = await _blob(session, 4, "d" * 64)
    t = await _track(
        session,
        title="E",
        genre="Pop",
        play_count=0,
        uploader=u,
        blob=b,
    )
    svc = GenreSamplesService(session)
    clip = await svc.ensure_preview_clip(t.id)
    assert clip.start_sec == 30.0
    assert clip.duration_sec == 15.0
    again = await svc.ensure_preview_clip(t.id)
    assert again.track_id == clip.track_id


async def test_add_remove_list_curated(
    session: AsyncSession,
) -> None:
    u = await _user(session, 90003)
    b = await _blob(session, 5, "e" * 64)
    t = await _track(
        session,
        title="A",
        genre="Pop",
        play_count=0,
        uploader=u,
        blob=b,
    )
    svc = GenreSamplesService(session)
    row = await svc.add_curated("Blues", t.id, position=1)
    listed = await svc.list_curated("Blues")
    assert len(listed) == 1
    assert listed[0].id == row.id
    ok = await svc.remove_curated(row.id)
    assert ok
    assert await svc.list_curated("Blues") == []
