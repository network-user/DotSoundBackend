"""Tests for DedupeService — per-user audio_hash lookup + source-hash lookup."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.dedupe_service import DedupeService

pytestmark = pytest.mark.anyio


async def _make_user(session: AsyncSession, tg_id: int):
    repo = UserRepository(session)
    user, _ = await repo.upsert(tg_id, f"u{tg_id}", f"U {tg_id}", None)
    return user


async def _make_track(
    session: AsyncSession,
    *,
    uploader_id: int,
    audio_hash: str | None,
    title: str = "T",
    is_active: bool = True,
    source_sha256: str | None = None,
):
    repo = TrackRepository(session)
    return await repo.create(
        title=title,
        artist=None,
        genre=None,
        source="internal",
        catalog_type="ugc",
        access_mode="internal_stream",
        file_key=None,
        cover_key=None,
        uploaded_by_id=uploader_id,
        is_public=True,
        processing_status="active",
        file_size_bytes=1024,
        audio_hash=audio_hash,
        is_active=is_active,
        source_sha256=source_sha256,
    )


async def test_find_returns_match_for_same_user(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 3001)
    h = "a" * 64
    await _make_track(session, uploader_id=user.id, audio_hash=h)
    svc = DedupeService(session)
    found = await svc.find_for_user(user_id=user.id, audio_hash=h)
    assert found is not None
    assert found.audio_hash == h


async def test_find_returns_none_when_no_match(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 3002)
    await _make_track(
        session, uploader_id=user.id, audio_hash="b" * 64
    )
    svc = DedupeService(session)
    found = await svc.find_for_user(user_id=user.id, audio_hash="c" * 64)
    assert found is None


async def test_cross_user_isolation(session: AsyncSession) -> None:
    owner = await _make_user(session, 3003)
    other = await _make_user(session, 3004)
    h = "d" * 64
    await _make_track(session, uploader_id=owner.id, audio_hash=h)
    svc = DedupeService(session)
    # Other user must NOT see owner's track even with same hash.
    assert (
        await svc.find_for_user(user_id=other.id, audio_hash=h)
        is None
    )


async def test_inactive_track_ignored(session: AsyncSession) -> None:
    user = await _make_user(session, 3005)
    h = "e" * 64
    await _make_track(
        session,
        uploader_id=user.id,
        audio_hash=h,
        is_active=False,
    )
    svc = DedupeService(session)
    assert (
        await svc.find_for_user(user_id=user.id, audio_hash=h) is None
    )


async def test_find_by_source_sha256_per_user(
    session: AsyncSession,
) -> None:
    """The server-side source-hash lookup is still scoped per user
    because cross-user dedup happens transparently at finalize time
    (not via this endpoint)."""
    user = await _make_user(session, 3006)
    other = await _make_user(session, 3007)
    src = "f" * 64
    await _make_track(
        session,
        uploader_id=user.id,
        audio_hash=None,
        source_sha256=src,
    )
    svc = DedupeService(session)
    own = await svc.find_for_user_by_source(
        user_id=user.id, source_sha256=src
    )
    assert own is not None
    assert own.source_sha256 == src
    other_lookup = await svc.find_for_user_by_source(
        user_id=other.id, source_sha256=src
    )
    assert other_lookup is None
