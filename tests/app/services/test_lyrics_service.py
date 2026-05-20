from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services import compute_router, lyrics_cascade, lyrics_worker
from app.services.lyrics_service import (
    LyricsService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1400,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(telegram_id, "u", "Test", None)
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T",
        file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_create_or_update_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    lyrics = await svc.create_or_update(tid, uid, "Line 1\nLine 2")

    assert lyrics.plain_text == "Line 1\nLine 2"
    assert lyrics.track_id == tid


async def test_get_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Hello World")

    result = await svc.get_lyrics(tid, uid)

    assert result is not None
    assert result.plain_text == "Hello World"


async def test_get_lyrics_track_not_found(
    session: AsyncSession,
) -> None:
    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_lyrics(9999)

    assert exc.value.status_code == 404


async def test_create_lyrics_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 1401)
    uid2 = await _make_user(session, 1402)
    tid = await _make_track(session, uid1)

    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.create_or_update(tid, uid2, "text")

    assert exc.value.status_code == 403


async def _make_external_track(session: AsyncSession, owner_id: int) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="External",
        sc_url="https://soundcloud.com/x/y",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source="soundcloud",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_external_reference_blocks_owner_edits(
    session: AsyncSession,
) -> None:
    owner_id = await _make_user(session, telegram_id=1410)
    tid = await _make_external_track(session, owner_id)

    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.create_or_update(tid, owner_id, "text")

    assert exc.value.status_code == 403


async def test_external_reference_allows_admin_edits(
    session: AsyncSession,
) -> None:
    from app.repositories.user import UserRepository

    owner_id = await _make_user(session, telegram_id=1411)
    tid = await _make_external_track(session, owner_id)
    user_repo = UserRepository(session)
    admin, _ = await user_repo.upsert(
        telegram_id=1412,
        username="admin",
        first_name="Admin",
        last_name=None,
    )
    admin.is_admin = True
    await session.flush()

    svc = LyricsService(session)
    lyrics = await svc.create_or_update(tid, admin.id, "Admin-edited")

    assert lyrics.plain_text == "Admin-edited"


async def test_ugc_owner_can_still_edit(
    session: AsyncSession,
) -> None:
    owner_id = await _make_user(session, telegram_id=1413)
    tid = await _make_track(session, owner_id)

    svc = LyricsService(session)
    lyrics = await svc.create_or_update(tid, owner_id, "ugc-text")

    assert lyrics.plain_text == "ugc-text"


async def test_delete_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "text")

    removed = await svc.delete_lyrics(tid, uid)

    assert removed is True


async def test_delete_lyrics_not_existing(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    removed = await svc.delete_lyrics(tid, uid)

    assert removed is False


async def test_update_sync(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Line 1")

    synced = [{"time": 0, "text": "Line 1"}]
    lyrics = await svc.update_sync(tid, uid, synced)

    assert lyrics.synced_lines == synced


async def test_update_sync_no_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.update_sync(tid, uid, [{"time": 0, "text": "X"}])

    assert exc.value.status_code == 404


async def test_trigger_sync_for_existing_text_skips_catalog_tier(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Line 1\nLine 2")

    captured: dict[str, object] = {}

    async def fake_start_cascade(
        _session: AsyncSession,
        *,
        job: LyricsJob,
        with_sync: bool,
        bypass_cache: bool,
        skip_tiers: tuple[str, ...] = (),
        skip_reason: str | None = None,
    ) -> str:
        captured["with_sync"] = with_sync
        captured["bypass_cache"] = bypass_cache
        captured["skip_tiers"] = skip_tiers
        captured["skip_reason"] = skip_reason
        captured["job_profile"] = job.profile
        job.profile = "gpu_full"
        job.current_tier = "remote_whisper"
        job.status = "queued"
        return "remote_whisper"

    monkeypatch.setattr(
        compute_router,
        "get_routing_mode",
        AsyncMock(return_value="auto"),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_cached_lyrics_result",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_lyrics_progress",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_cascade,
        "start_cascade",
        fake_start_cascade,
    )

    task_id = await svc.trigger_auto_generation(
        tid,
        uid,
        with_sync=True,
    )

    assert task_id
    assert captured["with_sync"] is True
    assert captured["skip_tiers"] == ("catalog_only",)
    assert captured["skip_reason"] == "existing_text_needs_timing"


async def test_trigger_sync_ignores_stale_lines_without_time_ms(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Line 1\nLine 2")
    existing = (
        await session.execute(
            select(TrackLyrics).where(TrackLyrics.track_id == tid)
        )
    ).scalar_one()
    existing.synced_lines = [{"text": "Line 1"}]
    await session.flush()

    captured: dict[str, object] = {}

    async def fake_start_cascade(
        _session: AsyncSession,
        *,
        job: LyricsJob,
        with_sync: bool,
        bypass_cache: bool,
        skip_tiers: tuple[str, ...] = (),
        skip_reason: str | None = None,
    ) -> str:
        captured["with_sync"] = with_sync
        captured["skip_tiers"] = skip_tiers
        captured["skip_reason"] = skip_reason
        job.profile = "gpu_full"
        job.current_tier = "remote_whisper"
        job.status = "queued"
        return "remote_whisper"

    monkeypatch.setattr(
        compute_router,
        "get_routing_mode",
        AsyncMock(return_value="auto"),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_cached_lyrics_result",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_lyrics_progress",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_cascade,
        "start_cascade",
        fake_start_cascade,
    )

    task_id = await svc.trigger_auto_generation(
        tid,
        uid,
        with_sync=True,
    )

    assert task_id
    assert captured["with_sync"] is True
    assert captured["skip_tiers"] == ("catalog_only",)
    assert captured["skip_reason"] == "existing_text_needs_timing"


async def test_redefine_sync_clears_existing_timing_and_queues_job(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Line 1\nLine 2")
    await svc.update_sync(
        tid,
        uid,
        [{"time_ms": 0, "text": "Line 1"}],
    )
    existing = (
        await session.execute(
            select(TrackLyrics).where(TrackLyrics.track_id == tid)
        )
    ).scalar_one()
    existing.sync_quality = "line"
    existing.sync_profile = "gpu_full"
    existing.sync_source_name = "old-aligner"
    await session.flush()

    captured: dict[str, object] = {}

    async def fake_start_cascade(
        _session: AsyncSession,
        *,
        job: LyricsJob,
        with_sync: bool,
        bypass_cache: bool,
        skip_tiers: tuple[str, ...] = (),
        skip_reason: str | None = None,
    ) -> str:
        captured["with_sync"] = with_sync
        captured["bypass_cache"] = bypass_cache
        captured["skip_tiers"] = skip_tiers
        captured["skip_reason"] = skip_reason
        job.profile = "gpu_full"
        job.current_tier = "remote_whisper"
        job.status = "queued"
        return "remote_whisper"

    monkeypatch.setattr(
        compute_router,
        "get_routing_mode",
        AsyncMock(return_value="auto"),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "invalidate_cached_lyrics_for_track",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_cached_lyrics_result",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_worker,
        "set_lyrics_progress",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lyrics_cascade,
        "start_cascade",
        fake_start_cascade,
    )

    task_id = await svc.redefine_lyrics(
        tid,
        uid,
        with_sync=True,
    )

    assert task_id
    assert captured["with_sync"] is True
    assert captured["skip_tiers"] == ("catalog_only",)
    assert captured["skip_reason"] == "existing_text_needs_timing"
    job = (
        await session.execute(
            select(LyricsJob).where(LyricsJob.track_id == tid)
        )
    ).scalar_one()
    assert job.profile == "gpu_full"
    reloaded = (
        await session.execute(
            select(TrackLyrics).where(TrackLyrics.track_id == tid)
        )
    ).scalar_one()
    assert reloaded.plain_text == "Line 1\nLine 2"
    assert reloaded.synced_lines is None
    assert reloaded.sync_quality is None
    assert reloaded.sync_profile is None
    assert reloaded.sync_source_name is None


async def test_upsert_and_list_translations(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session, telegram_id=1414)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Hello")

    await svc.upsert_translation(
        tid, uid, "EN", "Hello EN"
    )
    await svc.upsert_translation(
        tid, uid, "ru", "Privet"
    )
    items = await svc.list_translations(tid, uid)
    assert [x.language_code for x in items] == [
        "en",
        "ru",
    ]


async def test_delete_translation(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session, telegram_id=1415)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)
    await svc.create_or_update(tid, uid, "Hello")
    await svc.upsert_translation(
        tid, uid, "en", "Hello EN"
    )

    removed = await svc.delete_translation(
        tid, uid, "en"
    )
    assert removed is True


async def test_upsert_translation_requires_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session, telegram_id=1416)
    tid = await _make_track(session, uid)
    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.upsert_translation(
            tid, uid, "en", "Hello EN"
        )
    assert exc.value.status_code == 404
