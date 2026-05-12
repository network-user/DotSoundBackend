from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.playback_variant_service import PlaybackVariantService
from app.services.track_response_build import build_track_response

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
