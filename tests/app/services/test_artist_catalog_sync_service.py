from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track
from app.services.artist_catalog_sync_service import (
    DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND,
    ArtistCatalogSyncService,
)
from app.services.soundcloud_service import (
    SoundCloudStationNotAvailable,
    synthetic_soundcloud_id_for_artist_station,
)

pytestmark = pytest.mark.anyio


@patch(
    "app.services.soundcloud_service.SoundCloudService."
    "try_autofill_soundcloud_user_id_for_artist",
    new_callable=AsyncMock,
)
async def test_sync_full_requires_soundcloud_user_id(
    autofill_sc_user: AsyncMock,
    session: AsyncSession,
) -> None:
    autofill_sc_user.return_value = False
    artist = Artist(name="A", name_normalized="a")
    session.add(artist)
    await session.flush()

    svc = ArtistCatalogSyncService(session)
    with pytest.raises(ValueError, match="soundcloud_user_id"):
        await svc.sync_full_artist(artist.id)
    autofill_sc_user.assert_awaited_once_with(artist.id)


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
    mock_sc.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.list_user_albums = AsyncMock(
        return_value=(
            [
                {
                    "id": 777,
                    "title": "Locked",
                    "tracks": [],
                },
            ],
            False,
        ),
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": synthetic_soundcloud_id_for_artist_station(50),
            "tracks": [],
            "artwork_url": None,
        },
    )
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )

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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.list_user_albums = AsyncMock(
        return_value=(
            [
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
            False,
        ),
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": synthetic_soundcloud_id_for_artist_station(999),
            "tracks": [
                {
                    "id": 202,
                    "permalink_url": "https://soundcloud.com/act/st",
                    "title": "Station",
                    "user": {"username": "Act"},
                    "duration": 5000,
                    "uri": "sc:st",
                },
            ],
            "artwork_url": None,
        },
    )

    svc = ArtistCatalogSyncService(session)
    stats = await svc.sync_full_artist(artist.id)

    assert stats["albums_synced"] == 1
    assert stats.get("station_synced") is True
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
        (
            await session.execute(
                select(ArtistCatalogReleaseTrack).where(
                    ArtistCatalogReleaseTrack.release_id == rel.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 1
    assert links[0].position == 0
    assert stats.get("albums_source_truncated") is False
    assert mock_inst.import_or_get_track.await_count == 2
    st_rel = (
        await session.execute(
            select(ArtistCatalogRelease).where(
                ArtistCatalogRelease.artist_id == artist.id,
                ArtistCatalogRelease.release_kind
                == DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND,
            )
        )
    ).scalar_one()
    expect_sid = synthetic_soundcloud_id_for_artist_station(999)
    assert st_rel.soundcloud_album_id == expect_sid


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_sync_full_caps_releases(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.artist_catalog_sync_service."
        "CATALOG_SYNC_MAX_RELEASES_PER_FULL_RUN",
        2,
    )
    artist = Artist(
        name="Many",
        name_normalized="many",
        soundcloud_user_id=1,
    )
    session.add(artist)
    await session.flush()

    mock_inst = MagicMock()
    mock_sc_cls.return_value = mock_inst
    mock_inst.ensure_soundcloud_ids_for_artist = AsyncMock(
        return_value=True,
    )
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    albums_payload = [
        {"id": 10 + i, "title": f"R{i}", "tracks": []} for i in range(4)
    ]
    mock_inst.list_user_albums = AsyncMock(
        return_value=(albums_payload, False),
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock()
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": synthetic_soundcloud_id_for_artist_station(1),
            "tracks": [],
            "artwork_url": None,
        },
    )

    svc = ArtistCatalogSyncService(session)
    stats = await svc.sync_full_artist(artist.id)

    assert stats["albums_seen"] == 2
    assert stats["albums_synced"] == 2
    assert mock_inst.expand_playlist_stub_tracks.await_count == 2


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_sync_single_caps_tracks(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.artist_catalog_sync_service."
        "CATALOG_SYNC_MAX_TRACKS_PER_RELEASE",
        3,
    )
    artist = Artist(
        name="T",
        name_normalized="t",
        soundcloud_user_id=500,
    )
    session.add(artist)
    await session.flush()

    tracks = [
        {
            "id": 1000 + i,
            "permalink_url": f"https://soundcloud.com/t/x{i}",
            "title": f"Song{i}",
            "user": {"username": "T"},
            "duration": 1000,
            "uri": f"sc:{i}",
        }
        for i in range(5)
    ]

    async def _fake_import(
        tr: dict,
        uid: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> Track:
        t = Track(
            title=tr.get("title", "T"),
            artist="T",
            source="soundcloud",
            catalog_type="external_reference",
            access_mode="third_party_stream",
            imported_from="soundcloud",
            external_id=str(tr.get("id", "0")),
            sc_url=str(tr.get("permalink_url", "")),
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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.fetch_playlist_by_id = AsyncMock(
        return_value={
            "id": 77,
            "title": "EP",
            "user": {"id": 500},
            "tracks": tracks,
        },
    )
    mock_inst.expand_playlist_stub_tracks = AsyncMock(side_effect=lambda x: x)
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)

    svc = ArtistCatalogSyncService(session)
    await svc.sync_single_release(artist.id, 77)

    assert mock_inst.import_or_get_track.await_count == 3
    rel = (
        await session.execute(
            select(ArtistCatalogRelease).where(
                ArtistCatalogRelease.artist_id == artist.id,
                ArtistCatalogRelease.soundcloud_album_id == 77,
            )
        )
    ).scalar_one()
    links = (
        (
            await session.execute(
                select(ArtistCatalogReleaseTrack).where(
                    ArtistCatalogReleaseTrack.release_id == rel.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 3


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_sync_artist_similar_station_writes_release(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Zed",
        name_normalized="zed",
        soundcloud_user_id=12,
    )
    session.add(artist)
    await session.flush()

    async def _fake_import(
        tr: dict,
        uid: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> Track:
        t = Track(
            title=tr.get("title", "T"),
            artist="Zed",
            source="soundcloud",
            catalog_type="external_reference",
            access_mode="third_party_stream",
            imported_from="soundcloud",
            external_id=str(tr.get("id", "0")),
            sc_url=str(tr.get("permalink_url", "")),
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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": synthetic_soundcloud_id_for_artist_station(12),
            "tracks": [
                {
                    "id": 9001,
                    "permalink_url": "https://soundcloud.com/z/s",
                    "title": "S",
                    "user": {"username": "Z"},
                    "duration": 1000,
                    "uri": "sc:s",
                },
            ],
            "artwork_url": None,
        },
    )
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)

    svc = ArtistCatalogSyncService(session)
    out = await svc.sync_artist_similar_station(artist.id)

    assert out["status"] == "ok"
    sid = synthetic_soundcloud_id_for_artist_station(12)
    rel = (
        await session.execute(
            select(ArtistCatalogRelease).where(
                ArtistCatalogRelease.artist_id == artist.id,
                ArtistCatalogRelease.soundcloud_album_id == sid,
            )
        )
    ).scalar_one()
    assert "Похожее" in rel.title
    assert "Zed" in rel.title
    assert rel.release_kind == DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_force_station_sync_overwrites_manual_locked_release(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Force Seed",
        name_normalized="force seed",
        soundcloud_user_id=55,
    )
    session.add(artist)
    await session.flush()
    station_id = synthetic_soundcloud_id_for_artist_station(55)
    existing = ArtistCatalogRelease(
        artist_id=artist.id,
        title="Locked Station",
        release_kind=DOTSOUND_SC_ARTIST_STATION_RELEASE_KIND,
        soundcloud_album_id=station_id,
        display_position=7,
        manual_lock=True,
    )
    old_track = Track(
        title="Old",
        play_count=0,
        is_public=True,
        is_active=True,
    )
    session.add_all([existing, old_track])
    await session.flush()
    session.add(
        ArtistCatalogReleaseTrack(
            release_id=existing.id,
            track_id=old_track.id,
            position=0,
        )
    )
    await session.flush()

    async def _fake_import(
        tr: dict,
        uid: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> Track:
        t = Track(
            title=tr.get("title", "T"),
            artist="Real Similar",
            source="soundcloud",
            catalog_type="external_reference",
            access_mode="third_party_stream",
            imported_from="soundcloud",
            external_id=str(tr.get("id", "0")),
            sc_url=str(tr.get("permalink_url", "")),
            uploaded_by_id=None,
            is_public=True,
            is_active=True,
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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": station_id,
            "tracks": [
                {
                    "id": 9101,
                    "permalink_url": "https://soundcloud.com/similar/new",
                    "title": "New Similar",
                    "user": {"username": "Real Similar"},
                    "duration": 1000,
                    "uri": "sc:new",
                },
            ],
            "artwork_url": None,
        },
    )
    mock_inst.download_artwork_as_cover_key = AsyncMock(return_value=None)
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)

    svc = ArtistCatalogSyncService(session)
    out = await svc.sync_artist_similar_station(artist.id, force=True)

    assert out["status"] == "ok"
    assert out["forced"] is True
    await session.refresh(existing)
    assert existing.manual_lock is True
    assert existing.display_position == 7
    links = (
        (
            await session.execute(
                select(ArtistCatalogReleaseTrack).where(
                    ArtistCatalogReleaseTrack.release_id == existing.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 1
    new_track = await session.get(Track, links[0].track_id)
    assert new_track is not None
    assert new_track.title == "New Similar"


@patch(
    "app.services.artist_catalog_sync_service.SoundCloudService",
)
async def test_station_sync_does_not_link_foreign_tracks_to_seed(
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    """Regression: «Похожее: Giza» content used to be linked to Giza
    via TrackArtist, polluting `/artists/{giza}/tracks`. Station
    tracks belong to *other* artists and must not be linked to seed.
    """
    seed = Artist(
        name="Giza",
        name_normalized="giza",
        soundcloud_user_id=42,
    )
    session.add(seed)
    await session.flush()

    foreign_payload = {
        "id": 1234,
        "permalink_url": "https://soundcloud.com/recidiv/life-is-swag",
        "title": "life is swag",
        "user": {"username": "рецидив"},
        "duration": 92000,
        "uri": "sc:1234",
    }

    async def _fake_import(
        tr: dict,
        uid: int,
        *,
        skip_background_lyrics: bool = True,
    ) -> Track:
        user = tr.get("user") or {}
        t = Track(
            title=tr.get("title", "T"),
            artist=user.get("username") or "Unknown",
            source="soundcloud",
            catalog_type="external_reference",
            access_mode="third_party_stream",
            imported_from="soundcloud",
            external_id=str(tr.get("id", "0")),
            sc_url=str(tr.get("permalink_url", "")),
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
    mock_inst.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None,
    )
    mock_inst.fetch_expanded_artist_station_playlist = AsyncMock(
        return_value={
            "id": synthetic_soundcloud_id_for_artist_station(42),
            "tracks": [foreign_payload],
            "artwork_url": None,
        },
    )
    mock_inst.download_artwork_as_cover_key = AsyncMock(
        return_value=None,
    )
    mock_inst.import_or_get_track = AsyncMock(side_effect=_fake_import)

    svc = ArtistCatalogSyncService(session)
    out = await svc.sync_artist_similar_station(seed.id)
    assert out["status"] == "ok"

    track = (
        await session.execute(
            select(Track).where(
                Track.external_id == "1234",
                Track.imported_from == "soundcloud",
            )
        )
    ).scalar_one()

    seed_link = (
        await session.execute(
            select(TrackArtist).where(
                TrackArtist.artist_id == seed.id,
                TrackArtist.track_id == track.id,
            )
        )
    ).scalar_one_or_none()
    assert seed_link is None, (
        "Station tracks must NOT be linked to the seed artist "
        "via TrackArtist (would pollute popular-tracks)."
    )

    real_artist = (
        await session.execute(
            select(Artist).where(Artist.name_normalized == "рецидив")
        )
    ).scalar_one_or_none()
    assert real_artist is not None, (
        "Real artist must be created from the station track's "
        "artist string."
    )
    real_link = (
        await session.execute(
            select(TrackArtist).where(
                TrackArtist.artist_id == real_artist.id,
                TrackArtist.track_id == track.id,
            )
        )
    ).scalar_one_or_none()
    assert (
        real_link is not None
    ), "Station tracks must be linked to their real artist."


async def test_sync_artist_similar_station_not_available_returns_skipped(
    session: AsyncSession,
) -> None:
    """When SC has no station for this artist the sync skips gracefully."""
    artist = Artist(
        name="Clout",
        name_normalized="clout",
        soundcloud_user_id=9_000_001,
    )
    session.add(artist)
    await session.flush()

    mock_sc = MagicMock()
    mock_sc.sync_artist_soundcloud_uploader_profile = AsyncMock(
        return_value=None
    )
    mock_sc.ensure_soundcloud_ids_for_artist = AsyncMock(return_value=True)
    mock_sc.fetch_expanded_artist_station_playlist = AsyncMock(
        side_effect=SoundCloudStationNotAvailable(9_000_001, "resolve_404")
    )

    with patch(
        "app.services.artist_catalog_sync_service.SoundCloudService",
        return_value=mock_sc,
    ):
        svc = ArtistCatalogSyncService(session)
        result = await svc.sync_artist_similar_station(artist.id)

    assert result["status"] == "skipped"
    assert "no_station" in result["reason"]
