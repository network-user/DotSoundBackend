from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest
from botocore.exceptions import ClientError

from app.core.s3 import (
    build_cas_audio_key,
    delete_object,
    download_object,
    download_object_range,
    ensure_bucket_exists,
    get_presigned_url,
    put_cas_audio,
    upload_audio,
    upload_object,
    upload_voice,
)

pytestmark = pytest.mark.anyio

_MOD = "app.core.s3"


def _s3_client_mock() -> AsyncMock:
    client = AsyncMock()
    client.put_object = AsyncMock()
    client.delete_object = AsyncMock()
    client.get_object = AsyncMock()
    client.head_bucket = AsyncMock()
    client.create_bucket = AsyncMock()
    client.list_objects_v2 = AsyncMock(
        return_value={"Contents": []}
    )
    client.generate_presigned_url = AsyncMock(
        return_value="https://s3/presigned"
    )
    return client


def test_build_cas_audio_key() -> None:
    sha = "a" * 64
    k = build_cas_audio_key(sha, "mp3")
    assert k == f"blobs/aa/{sha}.mp3"


@patch(f"{_MOD}.get_s3_client")
@patch(f"{_MOD}.upload_object", new_callable=AsyncMock)
async def test_put_cas_audio(
    mock_uo: AsyncMock, mock_ctx: MagicMock
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx
    data = b"\x00" * 10
    sha = "b" * 64
    key = await put_cas_audio(data, sha, "mp3", "audio/mpeg")
    assert f"blobs/bb/{sha}" in key
    mock_uo.assert_awaited()


@patch(f"{_MOD}.get_s3_client")
async def test_upload_audio_with_user(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    key = await upload_audio(
        b"data", "mp3", "audio/mpeg", user_id=42
    )

    assert key.startswith("42/")
    assert key.endswith(".mp3")
    client.put_object.assert_awaited_once()


@patch(f"{_MOD}.get_s3_client")
async def test_upload_audio_anon(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    key = await upload_audio(
        b"data", "wav", "audio/wav"
    )

    assert key.startswith("anon/")


@patch(f"{_MOD}.get_s3_client")
async def test_get_presigned_url(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    url = await get_presigned_url("some/key.mp3")

    assert url == "https://s3/presigned"
    client.generate_presigned_url.assert_awaited_once()


@patch(f"{_MOD}.get_s3_client")
async def test_delete_object(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    await delete_object("old/key.mp3")

    client.delete_object.assert_awaited_once()


@patch(f"{_MOD}.get_s3_client")
async def test_download_object(
    mock_ctx: MagicMock,
) -> None:
    body_stream = AsyncMock()
    body_stream.read = AsyncMock(
        return_value=b"audio-data"
    )
    body_stream.__aenter__ = AsyncMock(
        return_value=body_stream
    )
    body_stream.__aexit__ = AsyncMock(
        return_value=False
    )
    client = _s3_client_mock()
    client.get_object = AsyncMock(
        return_value={
            "Body": body_stream,
        }
    )
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    data = await download_object("key.mp3")

    assert data == b"audio-data"


@patch(f"{_MOD}.get_s3_client")
async def test_download_object_range_no_range(
    mock_ctx: MagicMock,
) -> None:
    body_stream = AsyncMock()
    body_stream.read = AsyncMock(
        return_value=b"full-data"
    )
    body_stream.__aenter__ = AsyncMock(
        return_value=body_stream
    )
    body_stream.__aexit__ = AsyncMock(
        return_value=False
    )
    client = _s3_client_mock()
    client.get_object = AsyncMock(
        return_value={
            "Body": body_stream,
            "ContentLength": 9,
            "ContentType": "audio/mpeg",
        }
    )
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    data, length, cr, ct = (
        await download_object_range("key.mp3")
    )

    assert data == b"full-data"
    assert length == 9
    assert cr is None
    assert ct == "audio/mpeg"


@patch(f"{_MOD}.get_s3_client")
async def test_download_object_range_with_range(
    mock_ctx: MagicMock,
) -> None:
    body_stream = AsyncMock()
    body_stream.read = AsyncMock(
        return_value=b"part"
    )
    body_stream.__aenter__ = AsyncMock(
        return_value=body_stream
    )
    body_stream.__aexit__ = AsyncMock(
        return_value=False
    )
    client = _s3_client_mock()
    client.get_object = AsyncMock(
        return_value={
            "Body": body_stream,
            "ContentLength": 4,
            "ContentRange": "bytes 0-3/100",
            "ContentType": "audio/mpeg",
        }
    )
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    data, length, cr, ct = (
        await download_object_range(
            "key.mp3", "bytes=0-3"
        )
    )

    assert data == b"part"
    assert cr == "bytes 0-3/100"


@patch(f"{_MOD}.get_s3_client")
async def test_download_object_range_client_error(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    error_response = {
        "Error": {"Code": "NoSuchKey"}
    }
    client.get_object = AsyncMock(
        side_effect=ClientError(
            error_response, "GetObject"
        )
    )
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    with pytest.raises(ClientError):
        await download_object_range("missing.mp3")


@patch(f"{_MOD}.get_s3_client")
async def test_upload_object(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    await upload_object(
        "hls/1/master.m3u8",
        b"#EXTM3U",
        "application/vnd.apple.mpegurl",
    )

    client.put_object.assert_awaited_once()


@patch(f"{_MOD}.get_s3_client")
async def test_ensure_bucket_exists_already(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    await ensure_bucket_exists()

    client.head_bucket.assert_awaited_once()
    client.create_bucket.assert_not_awaited()


@patch(f"{_MOD}.get_s3_client")
async def test_ensure_bucket_creates_when_missing(
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    error_response = {
        "Error": {"Code": "404"}
    }
    client.head_bucket = AsyncMock(
        side_effect=ClientError(
            error_response, "HeadBucket"
        )
    )
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    await ensure_bucket_exists()

    client.create_bucket.assert_awaited_once()


@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}.get_s3_client")
async def test_ensure_bucket_retries_on_error(
    mock_ctx: MagicMock,
    mock_sleep: AsyncMock,
) -> None:
    client_ok = _s3_client_mock()

    fail_ctx = AsyncMock()
    fail_ctx.__aenter__ = AsyncMock(
        side_effect=ConnectionError("not ready")
    )
    fail_ctx.__aexit__ = AsyncMock(
        return_value=False
    )

    ok_ctx = AsyncMock()
    ok_ctx.__aenter__ = AsyncMock(
        return_value=client_ok
    )
    ok_ctx.__aexit__ = AsyncMock(
        return_value=False
    )

    mock_ctx.side_effect = [
        fail_ctx,
        ok_ctx,
        ok_ctx,
        ok_ctx,
        ok_ctx,
    ]

    await ensure_bucket_exists()

    assert mock_sleep.await_count >= 1


@patch(f"{_MOD}.get_s3_client")
@patch(
    "app.services.media_service.process_image",
    return_value=(
        b"webp-data",
        b"thumb-data",
        200,
        200,
    ),
)
async def test_upload_cover(
    mock_process: MagicMock,
    mock_ctx: MagicMock,
) -> None:
    from app.core.s3 import upload_image

    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    img_key, thumb_key, w, h = await upload_image(
        b"raw-image", "covers", max_size=800
    )

    assert img_key.endswith(".webp")
    assert thumb_key.endswith("_thumb.webp")
    assert w == 200
    assert h == 200
    assert client.put_object.await_count == 2


@patch(f"{_MOD}.get_s3_client")
@patch(
    "app.services.media_service.process_voice",
    new_callable=AsyncMock,
    return_value=(b"ogg", 5, [0.5] * 100),
)
async def test_upload_voice(
    mock_voice: AsyncMock,
    mock_ctx: MagicMock,
) -> None:
    client = _s3_client_mock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.return_value = ctx

    key, dur, wf = await upload_voice(
        b"raw", user_id=7
    )

    assert key.startswith("voice/7/")
    assert key.endswith(".ogg")
    assert dur == 5
    assert len(wf) == 100
