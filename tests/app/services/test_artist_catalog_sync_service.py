from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track
from app.services.artist_catalog_sync_service import ArtistCatalogSyncService

pytestmark = pytest.mark.anyio


async def test_sync_full_requires_soundcloud_user_id(
    session: AsyncSession,
) -> None:
    artist = Artist(name="A", name_normalized="a")
    session.add(artist)
    await session.flush()

    svc = ArtistCatalogSyncService(session)
    with pytest.raises(ValueError, match="soundcloud_user_id"):
        await svc.sync_full_artist(artist.id)


async def test_sync_single_wrong_playlist_owner(
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="A",
        name_normalized="a",
        soundcloud_user_id=100,
    )
    session.add(artist)
    await session.flush()

    mock_sc = MagicMock()
    mock_sc.ensure_soundcloud_ids_for_artist = AsyncMock(
        return_value=True,
    )
    mock_sc.fetch_playlist_by_id = AsyncMock(
        return_value={
            "id": 5,
            "user": {"id": 999},
            "tracks": [],
        },
    )
    mock_sc.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)

    with patch(
        "app.services.artist_catalog_sync_service.SoundCloudService",
        return_value=mock_sc,
    ):
        svc = ArtistCatalogSyncService(session)
        with pytest.raises(ValueError, match="playlist"):
            await svc.sync_single_release(artist.id, 5)


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_sync_full_skips_manual_lock(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="A",
        name_normalized="a",
        soundcloud_user_id=50,
    )
    session.add(artist)
    await session.flush()
    session.add(
        ArtistCatalogRelease(
            artist_id=artist.id,
            title="Locked",
            soundcloud_album_id=777,
            display_position=0,
            manual_lock=True,
        )
    )
    await session.flush()

    mock_inst = MagicMock()
    mock_sc_cls.return_value = mock_inst
    mock_inst.ensure_soundcloud_ids_for_artist = AsyncMock(
        return_value=True,
    )
    mock_inst.list_user_albums = AsyncMock(
        return_value=[
            {
                "id": 777,
                "title": "Locked",
                "tracks": [],
            },
        ],
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)

    svc = ArtistCatalogSyncService(session)
    stats = await svc.sync_full_artist(artist.id)

    assert stats["skipped_manual"] == 1
    assert stats["albums_synced"] == 0
    mock_inst.import_or_get_track.assert_not_called()


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_sync_full_imports_release_and_links(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Act",
        name_normalized="act",
        soundcloud_user_id=999,
    )
    session.add(artist)
    await session.flush()

    async def _fake_import(
        tr: dict,
        uid: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> Track:
        url = tr.get("permalink_url") or ""
        t = Track(
            title=tr.get("title", "T"),
            artist="Act",
            source="soundcloud",
            catalog_type="external_reference",
            access_mode="third_party_stream",
            imported_from="soundcloud",
            external_id=str(tr.get("id", "0")),
            sc_url=url or f"https://soundcloud.com/x/{tr.get('id')}",
            uploaded_by_id=None,
        )
        session.add(t)
        await session.flush()
        await session.refresh(t)
        return t

    mock_inst = MagicMock()
    mock_sc_cls.return_value = mock_inst
    mock_inst.ensure_soundcloud_ids_for_artist = AsyncMock(
        return_value=True,
    )
    mock_inst.list_user_albums = AsyncMock(
        return_value=[
            {
                "id": 42,
                "title": "Album",
                "playlist_type": "album",
                "release_date": "2024-06-01",
                "tracks": [
                    {
                        "id": 101,
                        "permalink_url": "https://soundcloud.com/act/t1",
                        "title": "One",
                        "user": {"username": "Act"},
                        "duration": 60000,
                        "uri": "sc:one",
                    },
                ],
            },
        ],
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)

    svc = ArtistCatalogSyncService(session)
    stats = await svc.sync_full_artist(artist.id)

    assert stats["albums_synced"] == 1
    rel = (
        await session.execute(
            select(ArtistCatalogRelease).where(
                ArtistCatalogRelease.artist_id == artist.id,
                ArtistCatalogRelease.soundcloud_album_id == 42,
            )
        )
    ).scalar_one()
    assert rel.title == "Album"
    assert rel.release_kind == "album"
    links = (
        await session.execute(
            select(ArtistCatalogReleaseTrack).where(
                ArtistCatalogReleaseTrack.release_id == rel.id,
            )
        )
    ).scalars().all()
    assert len(links) == 1
    assert links[0].position == 0
