from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.upload_service import (
    UploadService,
    _resolve_mime,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.upload_service"


def _audio_upload(
    name: str = "t.mp3",
    content_type: str = "audio/mpeg",
    data: bytes = b"\xff\xfb" + b"\x00" * 64,
) -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(data),
        headers={"content-type": content_type},
    )


def test_resolve_mime_from_content_type() -> None:
    f = _audio_upload(content_type="audio/mpeg")
    assert _resolve_mime(f) == "audio/mpeg"


def test_resolve_mime_fallback_to_filename() -> None:
    f = _audio_upload(
        name="t.mp3",
        content_type="application/octet-stream",
    )
    assert _resolve_mime(f) == "audio/mpeg"


@patch(
    "app.services.lyrics_worker.catalog_only_lyrics_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(f"{_MOD}.transcode_and_upload.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.generate_and_upload_cover.kiq", new_callable=AsyncMock)
async def test_upload_track_success(
    mock_cover: AsyncMock,
    mock_transcode: AsyncMock,
    mock_s3: AsyncMock,
    mock_lyrics_kiq: AsyncMock,
    session: AsyncSession,
) -> None:
    _t = MagicMock()
    _t.task_id = "test-lyrics-task"
    mock_lyrics_kiq.return_value = _t
    from app.repositories.user import (
        UserRepository,
    )

    repo = UserRepository(session)
    user, _ = await repo.upsert(
        1700, "u", "Test", None
    )

    svc = UploadService(session)
    track = await svc.upload_track(
        file=_audio_upload(),
        title="Test",
        artist=None,
        uploader_id=user.id,
    )

    assert track.title == "Test"
    assert track.processing_status == "processing"
    mock_transcode.assert_awaited_once()
    mock_cover.assert_awaited_once()


@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(f"{_MOD}.transcode_and_upload.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.generate_and_upload_cover.kiq", new_callable=AsyncMock)
async def test_upload_track_unsupported_mime(
    mock_cover: AsyncMock,
    mock_transcode: AsyncMock,
    mock_s3: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = UploadService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.upload_track(
            file=_audio_upload(
                content_type="video/mp4"
            ),
            title="Bad",
            artist=None,
        )

    assert exc.value.status_code == 415


@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(f"{_MOD}.transcode_and_upload.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.generate_and_upload_cover.kiq", new_callable=AsyncMock)
async def test_upload_track_too_large(
    mock_cover: AsyncMock,
    mock_transcode: AsyncMock,
    mock_s3: AsyncMock,
    session: AsyncSession,
) -> None:
    big = b"\x00" * (101 * 1024 * 1024)
    svc = UploadService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.upload_track(
            file=_audio_upload(data=big),
            title="Big",
            artist=None,
        )

    assert exc.value.status_code == 413


@patch(
    "app.services.lyrics_worker.catalog_only_lyrics_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(f"{_MOD}.transcode_and_upload.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.generate_and_upload_cover.kiq", new_callable=AsyncMock)
async def test_upload_track_sets_provisional_file_key(
    mock_cover: AsyncMock,
    mock_transcode: AsyncMock,
    mock_s3: AsyncMock,
    mock_lyrics_kiq: AsyncMock,
    session: AsyncSession,
) -> None:
    """Regression: a freshly uploaded UGC track must be playable
    BEFORE the background transcode finishes. Storing the raw S3 key
    as the provisional ``file_key`` lets ``/audio?force_progressive``
    stream the original file immediately; the transcode pipeline
    overwrites ``file_key`` with the MP3 blob key when it completes.
    Without this, the player hangs on "buffering" forever for tracks
    uploaded via Telegram while the transcode queue catches up.
    """
    _t = MagicMock()
    _t.task_id = "test-lyrics-task"
    mock_lyrics_kiq.return_value = _t
    from app.repositories.user import UserRepository

    repo = UserRepository(session)
    user, _ = await repo.upsert(1701, "u2", "Probe", None)

    svc = UploadService(session)
    track = await svc.upload_track(
        file=_audio_upload(),
        title="Probe",
        artist=None,
        uploader_id=user.id,
    )

    assert track.file_key, (
        "UGC track must expose a playable file_key right after upload"
    )
    assert track.file_key.startswith("temp/raw/"), (
        f"expected provisional raw_key, got {track.file_key!r}"
    )
