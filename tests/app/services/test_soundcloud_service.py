from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.services.soundcloud_service import (
    SoundCloudService,
    normalize_soundcloud_permalink,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.soundcloud_service"


async def test_search_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = (
        MagicMock()
    )
    mock_response.json.return_value = {
        "collection": [
            {
                "kind": "track",
                "streamable": True,
                "title": "Song",
            },
            {
                "kind": "playlist",
                "streamable": True,
            },
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    tracks = await svc.search("test")

    assert len(tracks) == 1
    assert tracks[0]["title"] == "Song"


async def test_resolve_url_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url(
            "https://soundcloud.com/x"
        )

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_not_found(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url(
            "https://soundcloud.com/x/y"
        )

    assert exc.value.status_code == 404


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_401_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url("https://sc.com/x")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "id": 123,
        "title": "Track",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.resolve_url(
        "https://sc.com/x"
    )

    assert result["title"] == "Track"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_no_transcoding(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {"transcodings": []},
        "track_authorization": "",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=resolve_resp
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_stream_info(
            "https://sc.com/no-transcode-empty"
        )

    assert exc.value.status_code == 422


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/stream",
                    "format": {
                        "protocol": "progressive"
                    },
                    "snipped": False,
                }
            ]
        },
        "track_authorization": "auth",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {
        "url": "https://cdn/audio.mp3"
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, stream_resp]
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url, protocol = await svc.get_stream_info(
        "https://sc.com/x"
    )

    assert url == "https://cdn/audio.mp3"
    assert protocol == "progressive"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_url(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/s",
                    "format": {
                        "protocol": "progressive"
                    },
                }
            ]
        },
        "track_authorization": "",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {
        "url": "https://cdn/audio.mp3"
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, stream_resp]
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url = await svc.get_stream_url(
        "https://sc.com/y-get-stream-url"
    )

    assert url == "https://cdn/audio.mp3"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_no_client_id(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)
    result = await svc.get_charts()
    assert result == []


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "collection": [
            {
                "track": {
                    "id": 1,
                    "title": "Hit",
                    "streamable": True,
                }
            },
            {"track": None},
            {"track": {"id": 2, "streamable": False}},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.get_charts(genre="rock", limit=10)

    assert len(result) == 1
    assert result[0]["title"] == "Hit"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_error_returns_empty(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.get_charts()
    assert result == []


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_trending_delegates_to_charts(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"collection": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.get_trending(limit=5)
    assert result == []


@patch(
    "app.services.track_ingest_schedule_service"
    ".schedule_new_track_background_jobs",
    new_callable=AsyncMock,
)
async def test_import_or_get_track_sets_provenance(
    _sched: object,
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("test_id", session)
    sc_url = "https://soundcloud.com/test/track"
    track = await svc.import_or_get_track(
        {
            "permalink_url": sc_url,
            "title": "Imported Track",
            "user": {"username": "Artist"},
            "duration": 123000,
            "uri": "sc:track",
        },
        uploader_id=1,
    )

    assert track.source == "soundcloud"
    assert track.catalog_type == "external_reference"
    assert track.access_mode == "third_party_stream"
    assert track.source_platform == "soundcloud"
    assert track.source_url == sc_url
    assert track.canonical_source_url == sc_url
    assert track.source_name == "SoundCloud"


@patch(
    "app.services.track_ingest_schedule_service"
    ".schedule_new_track_background_jobs",
    new_callable=AsyncMock,
)
async def test_import_or_get_track_dedup_via_unique_index(
    _sched: object,
    session: AsyncSession,
) -> None:
    # Importing the same SC URL twice in a row must return the
    # first row, not create a duplicate (the partial unique index
    # on tracks.sc_url + ON CONFLICT DO NOTHING handle the race).
    svc = SoundCloudService("test_id", session)
    sc_url = "https://soundcloud.com/dedup/case"
    sc_data = {
        "permalink_url": sc_url,
        "title": "Same Song",
        "user": {"username": "Artist"},
        "duration": 90000,
        "uri": "sc:dedup",
    }

    first = await svc.import_or_get_track(sc_data, uploader_id=1)
    second = await svc.import_or_get_track(sc_data, uploader_id=2)

    assert first.id == second.id
    assert first.uploaded_by_id == 1


def test_normalize_soundcloud_permalink_slug() -> None:
    assert (
        normalize_soundcloud_permalink(
            "https://soundcloud.com/MyArtist/tracks"
        )
        == "myartist"
    )
    assert normalize_soundcloud_permalink("PlainSlug") == "plainslug"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_list_user_albums_pagination(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.raise_for_status = MagicMock()
    resp1.json.return_value = {
        "collection": [{"id": 10, "title": "One"}],
        "next_href": "https://api-v2.soundcloud.com/page2",
    }
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.raise_for_status = MagicMock()
    resp2.json.return_value = {
        "collection": [{"id": 11, "title": "Two"}],
        "next_href": None,
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resp1, resp2]
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    albums = await svc.list_user_albums(12345)

    assert len(albums) == 2
    assert albums[0]["id"] == 10
    assert albums[1]["id"] == 11


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_expand_playlist_stub_tracks(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    fetch_resp = MagicMock()
    fetch_resp.status_code = 200
    fetch_resp.raise_for_status = MagicMock()
    fetch_resp.json.return_value = {
        "id": 77,
        "permalink_url": "https://soundcloud.com/u/full",
        "title": "Resolved",
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=fetch_resp)
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.expand_playlist_stub_tracks(
        {"tracks": [{"id": 77}]}
    )

    assert result["tracks"][0]["title"] == "Resolved"


async def test_ensure_soundcloud_ids_applies(
    session: AsyncSession,
) -> None:
    artist = Artist(name="Act", name_normalized="act")
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        424242,
        "https://soundcloud.com/scuser/extra",
    )

    assert ok is True
    await session.refresh(artist)
    assert artist.soundcloud_user_id == 424242
    assert artist.soundcloud_permalink == "scuser"


async def test_ensure_soundcloud_ids_idempotent_same_user(
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Act",
        name_normalized="act2",
        soundcloud_user_id=99,
        soundcloud_permalink="oldslug",
    )
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        99,
        "newslug",
    )

    assert ok is True
    await session.refresh(artist)
    assert artist.soundcloud_permalink == "newslug"


async def test_ensure_soundcloud_ids_skips_on_user_mismatch(
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Act",
        name_normalized="act3",
        soundcloud_user_id=1,
    )
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        2,
        None,
    )

    assert ok is False
    await session.refresh(artist)
    assert artist.soundcloud_user_id == 1


async def test_ensure_soundcloud_ids_skips_when_sc_id_taken(
    session: AsyncSession,
) -> None:
    a1 = Artist(
        name="First",
        name_normalized="first",
        soundcloud_user_id=500,
    )
    a2 = Artist(name="Second", name_normalized="second")
    session.add_all([a1, a2])
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        a2.id,
        500,
        None,
    )

    assert ok is False
    await session.refresh(a2)
    assert a2.soundcloud_user_id is None
