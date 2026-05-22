from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def _set_track_video_key(
    db_session: AsyncSession, track_id: int, key: str
) -> None:
    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(video_key=key)
    )
    await db_session.commit()


async def test_upload_valid_mp3(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60001)
    track = await create_test_track(
        client, "Test Track", user["id"]
    )
    assert track["title"] == "Test Track"
    assert "file_key" in track


async def test_upload_invalid_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60002)
    headers = await auth_headers(
        client, user["id"]
    )
    response = await client.post(
        "/api/v1/tracks/upload",
        data={
            "title": "Bad File",
            "upload_terms_accepted": "true",
        },
        files={
            "file": (
                "image.png",
                BytesIO(b"\x89PNG"),
                "image/png",
            )
        },
        headers=headers,
    )
    assert response.status_code == 415


async def test_upload_too_large(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60003)
    headers = await auth_headers(
        client, user["id"]
    )
    big_data = (
        b"\xff\xfb"
        + b"\x00" * (101 * 1024 * 1024)
    )
    response = await client.post(
        "/api/v1/tracks/upload",
        data={
            "title": "Huge",
            "upload_terms_accepted": "true",
        },
        files={
            "file": (
                "big.mp3",
                BytesIO(big_data),
                "audio/mpeg",
            )
        },
        headers=headers,
    )
    assert response.status_code == 413


async def test_upload_requires_terms_acceptance(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60005)
    headers = await auth_headers(
        client, user["id"]
    )
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "No Terms"},
        files={
            "file": (
                "track.mp3",
                BytesIO(b"\xff\xfb" + b"\x00" * 64),
                "audio/mpeg",
            )
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Upload terms must be accepted"
    )


async def test_chunked_upload_init_requires_terms_acceptance(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60051)
    headers = await auth_headers(
        client, user["id"]
    )
    response = await client.post(
        "/api/v1/tracks/upload/init",
        json={
            "filename": "track.mp3",
            "mime": "audio/mpeg",
            "total_size": 1024,
            "title": "No Terms",
            "upload_terms_accepted": False,
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Upload terms must be accepted"
    )


async def test_upload_stores_terms_acceptance(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.models.upload_meta import TrackUploadMeta

    user = await create_test_user(client, 60006)
    headers = await auth_headers(
        client, user["id"]
    )
    _lyrics_kiq = MagicMock()
    _lyrics_kiq.task_id = "test-lyrics-task"
    with patch(
        "app.core.s3.upload_object",
        new_callable=AsyncMock,
    ), patch(
        "app.services.file_validator.validate_audio",
        return_value=None,
    ), patch(
        "app.services.upload_service.transcode_and_upload.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.upload_service.generate_and_upload_cover.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.lyrics_worker.catalog_only_lyrics_task.kiq",
        new_callable=AsyncMock,
        return_value=_lyrics_kiq,
    ):
        response = await client.post(
            "/api/v1/tracks/upload",
            data={
                "title": "Accepted Terms",
                "upload_terms_accepted": "true",
            },
            files={
                "file": (
                    "track.mp3",
                    BytesIO(b"\xff\xfb" + b"\x00" * 64),
                    "audio/mpeg",
                )
            },
            headers=headers,
        )

    assert response.status_code == 201
    track_id = response.json()["id"]
    result = await db_session.execute(
        select(TrackUploadMeta).where(
            TrackUploadMeta.track_id == track_id
        )
    )
    meta = result.scalar_one()
    assert meta.upload_terms_accepted is True
    assert meta.upload_terms_version == "2026-04-15"


async def test_upload_no_artist(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60004)
    track = await create_test_track(
        client, "No Artist", user["id"]
    )
    assert track["title"] == "No Artist"


async def test_list_my_tracks(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60010)
    headers = await auth_headers(
        client, user["id"]
    )
    await create_test_track(
        client, "MyTrack1", user["id"]
    )
    await create_test_track(
        client, "MyTrack2", user["id"]
    )

    r = await client.get(
        "/api/v1/tracks/my", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


async def test_list_my_tracks_unauthorized(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/my")
    assert r.status_code in (401, 403)


async def test_delete_track(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60011)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "ToDelete", user["id"]
    )

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ):
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}",
            headers=headers,
        )
    assert r.status_code == 204


async def test_delete_external_import_only_unlinks_user_library(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await create_test_user(client, 60014)
    other = await create_test_user(client, 60015)
    owner_headers = await auth_headers(client, owner["id"])
    track = Track(
        title="Imported External",
        artist="Artist",
        uploaded_by_id=owner["id"],
        is_active=True,
        is_public=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        imported_from="soundcloud",
        sc_url="https://soundcloud.com/test/imported-external",
        source_url="https://soundcloud.com/test/imported-external",
    )
    db_session.add(track)
    await db_session.flush()
    from app.repositories.user_track_library import (
        UserTrackLibraryRepository,
    )

    library = UserTrackLibraryRepository(db_session)
    await library.add(owner["id"], track.id, source="soundcloud")
    await library.add(other["id"], track.id, source="soundcloud")
    await db_session.commit()

    r = await client.delete(
        f"/api/v1/tracks/{track.id}",
        headers=owner_headers,
    )

    assert r.status_code == 204
    await db_session.refresh(track)
    assert track.is_active is True
    assert track.deleted_at is None
    assert track.uploaded_by_id is None
    assert await library.has(owner["id"], track.id) is False
    assert await library.has(other["id"], track.id) is True


async def test_external_import_edit_context_denied_to_importer(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await create_test_user(client, 60016)
    headers = await auth_headers(client, owner["id"])
    track = Track(
        title="External Edit",
        artist="Artist",
        uploaded_by_id=owner["id"],
        is_active=True,
        is_public=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        imported_from="soundcloud",
        sc_url="https://soundcloud.com/test/external-edit",
    )
    db_session.add(track)
    await db_session.commit()

    r = await client.get(
        f"/api/v1/tracks/{track.id}/edit-context",
        headers=headers,
    )

    assert r.status_code == 403


async def test_delete_track_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60012)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.delete(
        "/api/v1/tracks/99999", headers=headers
    )
    assert r.status_code == 404


async def test_update_track_visibility(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60013)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VisTrack", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"is_public": False},
    )
    assert r.status_code == 200
    assert r.json()["is_public"] is False


async def test_update_track_no_fields(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60014)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "NoField", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={},
    )
    assert r.status_code == 400


async def test_update_track_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60015)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.patch(
        "/api/v1/tracks/99999",
        headers=headers,
        json={"is_public": False},
    )
    assert r.status_code == 404


async def test_upload_cover_unsupported_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60016)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "CoverTrack", user["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{track['id']}/cover",
        headers=headers,
        files={
            "cover": (
                "image.bmp",
                BytesIO(b"BM" + b"\x00" * 50),
                "image/bmp",
            )
        },
    )
    assert r.status_code == 415


async def test_upload_video_unsupported_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60017)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidTrack", user["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{track['id']}/video",
        headers=headers,
        files={
            "video": (
                "vid.avi",
                BytesIO(b"\x00" * 100),
                "video/avi",
            )
        },
    )
    assert r.status_code == 415


async def test_delete_video_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60018)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.delete(
        "/api/v1/tracks/99999/video",
        headers=headers,
    )
    assert r.status_code == 404


async def test_regenerate_cover_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60019)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.post(
        "/api/v1/tracks/99999/cover/generate",
        headers=headers,
    )
    assert r.status_code == 404


async def test_upload_video_success(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 60020)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidOK", user["id"]
    )
    await _set_track_video_key(
        db_session, track["id"], "videos/old.mp4"
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with (
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
        ),
        patch(
            "app.core.s3.delete_object",
            new_callable=AsyncMock,
        ) as mock_del,
        patch(
            "app.services.file_validator.validate_video",
            return_value="video/mp4",
        ),
        patch(
            "app.services.video_transcoding.transcode_video.kiq",
            new_callable=AsyncMock,
        ) as mock_kiq,
    ):
        r = await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["video_processing_status"] == "active"
    assert data.get("video_key")
    mock_del.assert_called_once_with("videos/old.mp4")
    mock_kiq.assert_not_awaited()


async def test_delete_video_success(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 60021)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidDel", user["id"]
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with (
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.file_validator.validate_video",
            return_value="video/mp4",
        ),
        patch(
            "app.services.video_transcoding.transcode_video.kiq",
            new_callable=AsyncMock,
        ),
    ):
        r = await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )
    upload_body = r.json()
    assert upload_body["video_processing_status"] == "active"
    assert upload_body.get("video_key")
    await _set_track_video_key(
        db_session, track["id"], "videos/vid1.mp4"
    )

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ) as mock_del:
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
        )
    assert r.status_code == 204
    mock_del.assert_called_once()
    result = await db_session.execute(
        select(Track).where(Track.id == track["id"])
    )
    saved = result.scalar_one()
    assert saved.video_key is None
    assert saved.video_processing_status is None


async def test_delete_processing_video_clears_stuck_status(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 60022)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidCancel", user["id"]
    )
    await db_session.execute(
        update(Track)
        .where(Track.id == track["id"])
        .values(video_processing_status="processing:stuck")
    )
    await db_session.commit()

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ) as mock_del:
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
        )

    assert r.status_code == 204
    mock_del.assert_not_called()
    result = await db_session.execute(
        select(Track).where(Track.id == track["id"])
    )
    saved = result.scalar_one()
    assert saved.video_key is None
    assert saved.video_processing_status is None
    assert saved.video_thumbnail_key is None


async def test_update_track_title(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60030)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "OldTitle", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"title": "NewTitle"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "NewTitle"


async def test_update_track_artist(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60031)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "ArtistTrack", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"artist": "New Artist"},
    )
    assert r.status_code == 200
    assert r.json()["artist"] == "New Artist"


async def test_update_track_genre(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60032)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "GenreTrack", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"genre": "Electronic"},
    )
    assert r.status_code == 200
    assert r.json()["genre"] == "Electronic"


async def test_update_track_description(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60033)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "DescTrack", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"description": "A great track"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "A great track"


async def test_update_track_multiple_fields(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60034)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "MultiField", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={
            "title": "Updated",
            "artist": "New Art",
            "genre": "Rock",
            "is_public": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Updated"
    assert data["artist"] == "New Art"
    assert data["genre"] == "Rock"
    assert data["is_public"] is False


async def test_update_track_non_owner(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 60035)
    other = await create_test_user(client, 60036)
    other_headers = await auth_headers(
        client, other["id"]
    )
    track = await create_test_track(
        client, "Owned", owner["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=other_headers,
        json={"title": "Hacked"},
    )
    assert r.status_code == 404


async def test_delete_track_cleans_video_s3(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 60022)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "CleanVid", user["id"]
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with (
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.file_validator.validate_video",
            return_value="video/mp4",
        ),
        patch(
            "app.services.video_transcoding.transcode_video.kiq",
            new_callable=AsyncMock,
        ),
    ):
        await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )
    await _set_track_video_key(
        db_session, track["id"], "videos/enc1.mp4"
    )

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ) as mock_del:
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}",
            headers=headers,
        )
    assert r.status_code == 204
    deleted_keys = [
        c.args[0] for c in mock_del.call_args_list
    ]
    assert any(
        k.startswith("videos/") for k in deleted_keys
    )
