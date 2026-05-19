from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.album import Album
from app.models.artist import Artist
from app.models.playlist import Playlist
from app.models.user import User
from app.services.promotion_service import (
    PromotionService,
    PromotionValidationError,
    UNSET,
)
from tests.factories import TrackFactory, UserFactory

pytestmark = pytest.mark.anyio


async def _create_user(session: AsyncSession) -> User:
    user = UserFactory()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_track(
    session: AsyncSession,
    *,
    uploaded_by_id: int,
    is_active: bool = True,
    is_public: bool = True,
):
    track = TrackFactory(
        uploaded_by_id=uploaded_by_id,
        is_active=is_active,
        is_public=is_public,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def _create_artist(session: AsyncSession) -> Artist:
    artist = Artist(
        name="Edge Case",
        name_normalized="edge case",
        source="internal",
    )
    session.add(artist)
    await session.flush()
    await session.refresh(artist)
    return artist


async def _create_playlist(
    session: AsyncSession,
    *,
    owner_id: int,
    is_public: bool = True,
) -> Playlist:
    playlist = Playlist(
        name="P",
        owner_id=owner_id,
        is_public=is_public,
        playlist_type="editorial",
    )
    session.add(playlist)
    await session.flush()
    await session.refresh(playlist)
    return playlist


async def _create_album(
    session: AsyncSession,
    *,
    owner_id: int,
    is_public: bool = True,
) -> Album:
    album = Album(title="A", owner_id=owner_id, is_public=is_public)
    session.add(album)
    await session.flush()
    await session.refresh(album)
    return album


async def test_create_validates_unknown_entity(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    svc = PromotionService(session)
    with pytest.raises(PromotionValidationError):
        await svc.create(
            entity_type="track",
            entity_id=99999,
            surfaces=["hero"],
            priority=0,
            starts_at=None,
            ends_at=None,
            is_active=True,
            title_override=None,
            subtitle_override=None,
            cta_label_override=None,
            cover_url_override=None,
            admin_user_id=admin.id,
        )


async def test_create_rejects_invalid_entity_type(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    svc = PromotionService(session)
    with pytest.raises(PromotionValidationError):
        await svc.create(
            entity_type="banner",
            entity_id=1,
            surfaces=["hero"],
            priority=0,
            starts_at=None,
            ends_at=None,
            is_active=True,
            title_override=None,
            subtitle_override=None,
            cta_label_override=None,
            cover_url_override=None,
            admin_user_id=admin.id,
        )


async def test_create_rejects_invalid_surface(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    with pytest.raises(PromotionValidationError):
        await svc.create(
            entity_type="artist",
            entity_id=artist.id,
            surfaces=["unknown_surface"],
            priority=0,
            starts_at=None,
            ends_at=None,
            is_active=True,
            title_override=None,
            subtitle_override=None,
            cta_label_override=None,
            cover_url_override=None,
            admin_user_id=admin.id,
        )


async def test_create_then_get_for_admin(session: AsyncSession) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero", "section"],
        priority=5,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override="Spotlight",
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    detail = await svc.get_for_admin(row.id)
    assert detail is not None
    assert detail.entity_label == "Edge Case"
    assert detail.availability == "available"
    assert set(detail.surfaces) == {"hero", "section"}


async def test_availability_hidden_for_unlisted_track(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    track = await _create_track(
        session, uploaded_by_id=admin.id, is_public=False
    )
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="track",
        entity_id=track.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    detail = await svc.get_for_admin(row.id)
    assert detail is not None
    assert detail.availability == "hidden"


async def test_get_for_surface_filters_unavailable(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    visible = await _create_track(session, uploaded_by_id=admin.id)
    hidden = await _create_track(
        session, uploaded_by_id=admin.id, is_public=False
    )
    svc = PromotionService(session)
    await svc.create(
        entity_type="track",
        entity_id=visible.id,
        surfaces=["hero"],
        priority=10,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    await svc.create(
        entity_type="track",
        entity_id=hidden.id,
        surfaces=["hero"],
        priority=20,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    items = await svc.get_for_surface("hero", user_id=None)
    assert [i.entity_id for i in items] == [visible.id]


async def test_override_falls_back_to_entity(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    items = await svc.get_for_surface("hero", user_id=None)
    assert items[0].title == "Edge Case"


async def test_override_used_when_provided(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override="Headliner",
        subtitle_override="Custom",
        cta_label_override="Tap",
        cover_url_override="/custom/cover.jpg",
        admin_user_id=admin.id,
    )
    items = await svc.get_for_surface("hero", user_id=None)
    assert items[0].title == "Headliner"
    assert items[0].subtitle == "Custom"
    assert items[0].cta_label == "Tap"
    assert items[0].cover_url == "/custom/cover.jpg"


async def test_update_with_partial_unset(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override="initial",
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    await svc.update(
        row,
        surfaces=None,
        priority=99,
        starts_at=UNSET,
        ends_at=UNSET,
        is_active=False,
        title_override=UNSET,
        subtitle_override=UNSET,
        cta_label_override=UNSET,
        cover_url_override=UNSET,
        admin_user_id=admin.id,
    )
    detail = await svc.get_for_admin(row.id)
    assert detail is not None
    assert detail.priority == 99
    assert detail.is_active is False
    assert detail.title_override == "initial"


async def test_update_rejects_inverted_window(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    now = datetime.now(UTC)
    row = await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    with pytest.raises(PromotionValidationError):
        await svc.update(
            row,
            surfaces=None,
            priority=None,
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=1),
            is_active=None,
            admin_user_id=admin.id,
        )


async def test_record_event_returns_false_when_inactive(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=False,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    ok = await svc.record_event(
        promotion_id=row.id,
        event_type="impression",
        surface="hero",
        user_id=None,
    )
    assert ok is False


async def test_record_event_rejects_invalid_type(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    artist = await _create_artist(session)
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="artist",
        entity_id=artist.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    with pytest.raises(PromotionValidationError):
        await svc.record_event(
            promotion_id=row.id,
            event_type="hover",
            surface="hero",
            user_id=None,
        )


async def test_stats_for_unknown_promotion(
    session: AsyncSession,
) -> None:
    svc = PromotionService(session)
    assert await svc.get_stats(99999) is None


async def test_stats_counts_impressions_and_clicks(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    track = await _create_track(session, uploaded_by_id=admin.id)
    svc = PromotionService(session)
    row = await svc.create(
        entity_type="track",
        entity_id=track.id,
        surfaces=["hero"],
        priority=0,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    for _ in range(4):
        await svc.record_event(
            promotion_id=row.id,
            event_type="impression",
            surface="hero",
            user_id=None,
        )
    await svc.record_event(
        promotion_id=row.id,
        event_type="click",
        surface="hero",
        user_id=None,
    )
    stats = await svc.get_stats(row.id, period_days=30)
    assert stats is not None
    assert stats.impressions == 4
    assert stats.clicks == 1
    assert stats.ctr == 0.25


async def test_playlist_and_album_resolution(
    session: AsyncSession,
) -> None:
    admin = await _create_user(session)
    pl = await _create_playlist(session, owner_id=admin.id)
    al = await _create_album(session, owner_id=admin.id)
    svc = PromotionService(session)
    await svc.create(
        entity_type="playlist",
        entity_id=pl.id,
        surfaces=["section"],
        priority=10,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    await svc.create(
        entity_type="album",
        entity_id=al.id,
        surfaces=["section"],
        priority=5,
        starts_at=None,
        ends_at=None,
        is_active=True,
        title_override=None,
        subtitle_override=None,
        cta_label_override=None,
        cover_url_override=None,
        admin_user_id=admin.id,
    )
    items = await svc.get_for_surface("section", user_id=None)
    titles = [i.title for i in items]
    assert "P" in titles
    assert "A" in titles
