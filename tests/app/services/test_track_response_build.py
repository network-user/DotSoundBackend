import asyncio
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

    async def spy_get_by_ids(
        self: AlbumRepository, album_ids: list[int]
    ) -> list[Album]:
        batch_calls.append(list(album_ids))
        return await original_get_by_ids(self, album_ids)

    async def spy_get_by_id(
        self: AlbumRepository, album_id: int
    ) -> Album | None:
        single_calls.append(album_id)
        return await original_get_by_id(self, album_id)

    async def fake_variant_batch(
        self: PlaybackVariantService, batch_tracks: list[Track]
    ) -> dict[int, list[int]]:
        return {t.id: [t.id] for t in batch_tracks}

    with (
        patch.object(AlbumRepository, "get_by_ids", spy_get_by_ids),
        patch.object(AlbumRepository, "get_by_id", spy_get_by_id),
        patch.object(
            PlaybackVariantService,
            "resolve_variant_track_ids_batch",
            fake_variant_batch,
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


async def test_build_track_responses_resolves_variants_in_one_batch(
    session: AsyncSession,
) -> None:
    """The listing builder must resolve variants sequentially in a
    single batch call and keep the concurrent gather free of any
    session I/O (a shared AsyncSession cannot be used concurrently).
    """
    owner = await _make_user(session, 3303)
    gid = "cccccccc-dddd-eeee-ffff-000000000000"
    t1 = await _make_track(session, owner, track_id_seed=21)
    t2 = await _make_track(session, owner, track_id_seed=22)
    t3 = await _make_track(session, owner, track_id_seed=23)
    for t in (t1, t2, t3):
        t.composition_group_id = gid
    await session.flush()

    batch_calls = 0
    original_batch = PlaybackVariantService.resolve_variant_track_ids_batch

    async def spy_batch(
        self: PlaybackVariantService, batch_tracks: list[Track]
    ) -> dict[int, list[int]]:
        nonlocal batch_calls
        batch_calls += 1
        return await original_batch(self, batch_tracks)

    single_calls = 0
    original_single = PlaybackVariantService.resolve_variant_track_ids

    async def spy_single(
        self: PlaybackVariantService, track: Track
    ) -> list[int]:
        nonlocal single_calls
        single_calls += 1
        return await original_single(self, track)

    real_execute = session.execute
    in_gather = {"depth": 0}

    async def guarded_execute(*args: object, **kwargs: object) -> object:
        if in_gather["depth"] > 0:
            raise AssertionError(
                "session.execute used inside the CPU-only gather"
            )
        return await real_execute(*args, **kwargs)

    real_gather = asyncio.gather

    async def flagging_gather(*aws: object, **kwargs: object) -> object:
        in_gather["depth"] += 1
        try:
            return await real_gather(*aws, **kwargs)
        finally:
            in_gather["depth"] -= 1

    with (
        patch.object(
            PlaybackVariantService,
            "resolve_variant_track_ids_batch",
            spy_batch,
        ),
        patch.object(
            PlaybackVariantService,
            "resolve_variant_track_ids",
            spy_single,
        ),
        patch.object(session, "execute", guarded_execute),
        patch.object(asyncio, "gather", flagging_gather),
    ):
        responses = await build_track_responses(session, [t1, t2, t3])

    assert batch_calls == 1
    # Composition-group tracks are resolved inside the batch query, so
    # the per-track single resolver is never touched for this listing.
    assert single_calls == 0
    assert len(responses) == 3
    # Every track is enriched with the full 3-member variant group,
    # built entirely from preloaded rows inside the gather.
    assert all(len(r.playback_variants) == 3 for r in responses)
