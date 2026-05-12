import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.album import Album
from app.models.track import Track
from app.models.user import User
from app.services.card_service import CardService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 2200,
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
    is_public: bool = True,
    cover_key: str | None = None,
) -> Track:
    track = Track(
        title="Test Song",
        file_key="k",
        uploaded_by_id=owner.id,
        is_public=is_public,
        cover_key=cover_key,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def test_get_card_success(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user)

    svc = CardService(session)
    card = await svc.get_card(track.id)

    assert card is not None
    assert card.id == track.id
    assert card.title == "Test Song"


async def test_get_card_not_found(
    session: AsyncSession,
) -> None:
    svc = CardService(session)

    card = await svc.get_card(9999)

    assert card is None


async def test_get_card_private_not_owner(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, 2201)
    other = await _make_user(session, 2202)
    track = await _make_track(session, owner, is_public=False)

    svc = CardService(session)
    card = await svc.get_card(track.id, requester_id=other.id)

    assert card is None


async def test_get_card_private_owner_sees(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session)
    track = await _make_track(session, owner, is_public=False)

    svc = CardService(session)
    card = await svc.get_card(track.id, requester_id=owner.id)

    assert card is not None


async def test_get_card_with_cover(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user, cover_key="covers/img.png")

    svc = CardService(session)
    card = await svc.get_card(track.id)

    assert card is not None
    assert card.cover_url is not None
    assert "covers" in card.cover_url


async def test_get_card_falls_back_to_album_cover(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    album = Album(
        owner_id=user.id,
        title="LP",
        cover_key="covers/album.webp",
    )
    session.add(album)
    await session.flush()
    track = Track(
        title="On LP",
        file_key="kf",
        uploaded_by_id=user.id,
        is_public=True,
        cover_key=None,
        album_id=album.id,
        album_position=1,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)

    svc = CardService(session)
    card = await svc.get_card(track.id)

    assert card is not None
    assert card.cover_url is not None
    assert "album.webp" in card.cover_url
