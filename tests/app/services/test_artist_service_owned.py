"""Tests for ArtistService.get_owned_for_user / update_owned_profile.

Covers: not-yet-created → 404, ensure creates row, patch updates
fields, country/birthplace/website coercion, name stays read-only.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.services.artist_service import ArtistService

pytestmark = pytest.mark.anyio


async def _user(session: AsyncSession, tg_id: int, display: str | None):
    repo = UserRepository(session)
    user, _ = await repo.upsert(tg_id, f"u{tg_id}", display, None)
    return user


async def test_get_owned_returns_none_initially(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9001, "Alice")
    svc = ArtistService(session)
    assert await svc.get_owned_for_user(user.id) is None


async def test_ensure_creates_owned_artist(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9002, "Bob")
    svc = ArtistService(session)
    artist = await svc.ensure_owned_artist_for_user(
        user_id=user.id, preferred_name="Bob"
    )
    assert artist.owner_user_id == user.id
    assert artist.name == "Bob"
    found = await svc.get_owned_for_user(user.id)
    assert found is not None
    assert found.id == artist.id


async def test_update_owned_profile_patches_fields(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9003, "Carol")
    svc = ArtistService(session)
    await svc.ensure_owned_artist_for_user(
        user_id=user.id, preferred_name="Carol"
    )
    patched = await svc.update_owned_profile(
        user_id=user.id,
        bio="indie producer",
        country="ru",
        birthplace="  Moscow  ",
        website_url="https://example.com",
    )
    assert patched.bio == "indie producer"
    assert patched.country == "RU"  # upper-cased + clamped to 2
    assert patched.birthplace == "Moscow"  # trimmed
    assert patched.website_url == "https://example.com"
    # name is read-only here; still equals display_name
    assert patched.name == "Carol"


async def test_update_owned_profile_clears_with_none(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9004, "Dan")
    svc = ArtistService(session)
    await svc.ensure_owned_artist_for_user(
        user_id=user.id, preferred_name="Dan"
    )
    await svc.update_owned_profile(
        user_id=user.id,
        bio="something",
    )
    cleared = await svc.update_owned_profile(
        user_id=user.id,
        bio=None,
    )
    assert cleared.bio is None


async def test_update_owned_profile_404_when_no_artist(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9005, "Eva")
    svc = ArtistService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.update_owned_profile(
            user_id=user.id, bio="anything"
        )
    assert exc.value.status_code == 404


async def test_update_owned_profile_ignores_unset_fields(
    session: AsyncSession,
) -> None:
    user = await _user(session, 9006, "Frank")
    svc = ArtistService(session)
    await svc.ensure_owned_artist_for_user(
        user_id=user.id, preferred_name="Frank"
    )
    # set bio explicitly, leave others as-is (= unset, sentinel ...)
    await svc.update_owned_profile(
        user_id=user.id, bio="original bio"
    )
    # update only country; bio stays
    patched = await svc.update_owned_profile(
        user_id=user.id, country="US"
    )
    assert patched.bio == "original bio"
    assert patched.country == "US"
