from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.album import Album
from app.models.track import Track
from app.models.user import User
from app.repositories.album import AlbumRepository
from app.services.playback_variant_service import PlaybackVariantService
from app.services.track_response_build import (
    build_track_response,
    build_track_responses,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 3300,
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_track(
    session: AsyncSession,
    owner: User,
    *,
    title: str = "Same",
    cover_key: str | None = None,
    play_count: int = 0,
    track_id_seed: int = 0,
) -> Track:
    track = Track(
        title=title,
        file_key=f"k{track_id_seed}",
        duration_seconds=180,
        uploaded_by_id=owner.id,
        is_public=True,
        cover_key=cover_key,
        play_count=play_count,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def test_build_track_response_borrows_cover_from_variant_group(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, 3301)
    bare = await _make_track(
        session,
        owner,
        cover_key=None,
        play_count=10,
        track_id_seed=1,
    )
    with_art = await _make_track(
        session,
        owner,
        cover_key="covers/variant.webp",
        play_count=0,
        track_id_seed=2,
    )

    with patch.object(
        PlaybackVariantService,
        "resolve_variant_track_ids",
        new=AsyncMock(
            return_value=sorted([bare.id, with_art.id]),
        ),
    ):
        resp = await build_track_response(
            session,
            bare,
            include_has_lyrics=False,
        )

    assert resp.cover_key == "covers/variant.webp"


async def test_build_track_responses_batches_album_cover_fetch(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, 3302)
    album = Album(
        owner_id=owner.id,
        title="Shared Album",
        cover_key="covers/album.webp",
        is_public=True,
    )
    session.add(album)
    await session.flush()
    await session.refresh(album)

    t1 = await _make_track(session, owner, cover_key=None, track_id_seed=11)
    t2 = await _make_track(session, owner, cover_key=None, track_id_seed=12)
    t3 = await _make_track(session, owner, cover_key=None, track_id_seed=13)
    for t in (t1, t2, t3):
        t.album_id = album.id
    await session.flush()

    original_get_by_ids = AlbumRepository.get_by_ids
    original_get_by_id = AlbumRepository.get_by_id
    batch_calls: list[list[int]] = []
    single_calls: list[int] = []

    async def spy_get_by_ids(self, album_ids):
        batch_calls.append(list(album_ids))
        return await original_get_by_ids(self, album_ids)

    async def spy_get_by_id(self, album_id):
        single_calls.append(album_id)
        return await original_get_by_id(self, album_id)

    with (
        patch.object(AlbumRepository, "get_by_ids", spy_get_by_ids),
        patch.object(AlbumRepository, "get_by_id", spy_get_by_id),
        patch.object(
            PlaybackVariantService,
            "resolve_variant_track_ids",
            new=AsyncMock(side_effect=lambda tr: [tr.id]),
        ),
    ):
        responses = await build_track_responses(session, [t1, t2, t3])

    assert len(batch_calls) == 1
    assert set(batch_calls[0]) == {album.id}
    assert single_calls == []
    assert [r.cover_key for r in responses] == [
        "covers/album.webp",
        "covers/album.webp",
        "covers/album.webp",
    ]
