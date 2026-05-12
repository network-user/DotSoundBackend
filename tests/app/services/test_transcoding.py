from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User

pytestmark = pytest.mark.anyio

_MOD = "app.services.transcoding"


async def _put_cas_side(
    _data: bytes, sha: str, ext: str, _ct: str
) -> str:
    from app.core.s3 import build_cas_audio_key

    return build_cas_audio_key(sha, ext)


async def _make_track(
    session: AsyncSession,
) -> Track:
    user = User(
        telegram_id=2100,
        username="u",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    track = Track(
        title="T",
        file_key=None,
        uploaded_by_id=user.id,
        processing_status="processing",
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


_RAW = b"\xff\xfb" + b"\x00" * 100


@patch(
    f"{_MOD}._update_track_status",
    new_callable=AsyncMock,
)
@patch(
    f"{_MOD}._upload_hls",
    new_callable=AsyncMock,
    return_value="hls/1/master.m3u8",
)
@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=_RAW,
)
@patch(
    f"{_MOD}.s3.delete_object",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.asyncio.create_subprocess_exec")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_transcode_and_upload_ffmpeg_fail(
    mock_session_local: AsyncMock,
    mock_exec: AsyncMock,
    mock_del: AsyncMock,
    mock_dl: AsyncMock,
    mock_upload: AsyncMock,
    mock_hls: AsyncMock,
    mock_status: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"error")
    )
    mock_proc.returncode = 1
    mock_exec.return_value = mock_proc

    from app.services.transcoding import (
        transcode_and_upload,
    )

    await transcode_and_upload(
        track.id, "temp/raw/1_t.mp3", "t.mp3"
    )

    mock_status.assert_awaited()
    args = mock_status.call_args
    assert args[0][1] == "error"


@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
async def test_upload_hls(
    mock_upload: AsyncMock,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    hi = tmp_path / "hi"
    lo = tmp_path / "lo"
    hi.mkdir()
    lo.mkdir()
    (hi / "playlist.m3u8").write_text("#EXTM3U")
    (hi / "000.ts").write_bytes(b"\x00" * 10)
    (lo / "playlist.m3u8").write_text("#EXTM3U")

    from app.services.transcoding import (
        _upload_hls,
    )

    result = await _upload_hls(
        99, str(hi), str(lo)
    )

    assert "master.m3u8" in result
    assert mock_upload.await_count >= 3


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_update_track_status(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.transcoding import (
        _update_track_status,
    )

    await _update_track_status(
        track.id, "active", "key.mp3", 1024
    )


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_update_track_status_with_hls(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.transcoding import (
        _update_track_status,
    )

    await _update_track_status(
        track.id,
        "active",
        "key.mp3",
        2048,
        hls_manifest_key="hls/1/master.m3u8",
    )

    await session.refresh(track)
    assert track.processing_status == "active"


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_update_track_status_not_found(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.transcoding import (
        _update_track_status,
    )

    await _update_track_status(
        99999, "error", None, None
    )


@patch(
    f"{_MOD}._upload_hls",
    new_callable=AsyncMock,
    return_value="hls/1/master.m3u8",
)
@patch(
    "app.core.s3.put_cas_audio",
    new_callable=AsyncMock,
    side_effect=_put_cas_side,
)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=_RAW,
)
@patch(
    f"{_MOD}.s3.delete_object",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.asyncio.create_subprocess_exec")
@patch("app.services.search_index_notify.schedule_reindex_track", new_callable=AsyncMock)
@patch("app.services.waveform_worker.generate_waveform_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_transcode_success(
    mock_session_local: AsyncMock,
    mock_waveform_kiq: AsyncMock,
    mock_reindex: AsyncMock,
    mock_exec: AsyncMock,
    mock_del: AsyncMock,
    mock_dl: AsyncMock,
    _mock_cas: AsyncMock,
    mock_hls: AsyncMock,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    mp3_path = tmp_path / "output.mp3"
    mp3_path.write_bytes(b"\xff\xfb" + b"\x00" * 50)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"")
    )
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    from app.services.transcoding import (
        transcode_and_upload,
    )

    with patch(
        f"{_MOD}.tempfile.mkdtemp",
        return_value=str(tmp_path),
    ), patch(
        f"{_MOD}.shutil.rmtree"
    ), patch(
        f"{_MOD}.os.makedirs"
    ):
        (tmp_path / "hi").mkdir(exist_ok=True)
        (tmp_path / "lo").mkdir(exist_ok=True)
        await transcode_and_upload(
            track.id, "temp/raw.mp3", "t.mp3"
        )

    await session.refresh(track)
    assert track.processing_status == "active"
    assert track.file_key
    assert str(track.file_key).startswith("blobs/")
    assert track.hls_manifest_key == "hls/1/master.m3u8"
    mock_reindex.assert_awaited()
    mock_waveform_kiq.assert_awaited_once_with(track.id)


def test_loudnorm_filter_in_ffmpeg_args() -> None:
    """_LOUDNORM_FILTER appears in every ffmpeg invocation."""
    import inspect

    from app.services import transcoding as mod

    src = inspect.getsource(mod.transcode_and_upload)
    assert mod._LOUDNORM_FILTER in src
    src_hls = inspect.getsource(mod.transcode_hls_only)
    assert mod._LOUDNORM_FILTER in src_hls


def test_parse_loudnorm_stats_valid() -> None:
    from app.services.transcoding import _parse_loudnorm_stats

    stderr = b"""
[Parsed_loudnorm_0 @ 0xdeadbeef] {
\t"input_i" : "-23.4",
\t"input_tp" : "-2.1",
\t"input_lra" : "9.2",
\t"input_thresh" : "-33.5",
\t"output_i" : "-14.0",
\t"output_tp" : "-1.0",
\t"output_lra" : "8.1",
\t"output_thresh" : "-24.1",
\t"normalization_type" : "dynamic",
\t"target_offset" : "0.0"
}"""
    stats = _parse_loudnorm_stats(stderr)
    assert stats is not None
    assert stats["input_i"] == "-23.4"
    assert stats["output_i"] == "-14.0"


def test_parse_loudnorm_stats_no_json() -> None:
    from app.services.transcoding import _parse_loudnorm_stats

    assert _parse_loudnorm_stats(b"no json here") is None


@patch(
    f"{_MOD}._update_track_status",
    new_callable=AsyncMock,
)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    side_effect=Exception("S3 down"),
)
@patch(
    f"{_MOD}.s3.delete_object",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_transcode_exception(
    mock_session_local: AsyncMock,
    mock_del: AsyncMock,
    mock_dl: AsyncMock,
    mock_status: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.transcoding import (
        transcode_and_upload,
    )

    await transcode_and_upload(
        track.id, "temp/raw.mp3", "t.mp3"
    )

    mock_status.assert_awaited()
    args = mock_status.call_args
    assert args[0][1] == "error"
