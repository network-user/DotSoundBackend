import sys
import types
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services.file_validator import (
    _mime_from_signatures,
    scan_for_malware,
    validate_audio,
    validate_image,
    validate_video,
)
from app.services.scan_service import ScanResult, ScanVerdict

pytestmark = pytest.mark.anyio


def _mock_from_buffer(data: bytes, mime: bool = True) -> str:
    mp3_sig = (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    if data.startswith(b"ID3") or data[0:2] in mp3_sig:
        return "audio/mpeg"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b"ftyp" in data[:32]:
        return "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3" or b"webm" in data[:200]:
        return "video/webm"
    return "application/octet-stream"


@pytest.fixture(autouse=True)
def _inject_magic_for_tests() -> Generator[None, None, None]:
    old = sys.modules.get("magic")
    fake = types.ModuleType("magic")
    fake.from_buffer = _mock_from_buffer
    sys.modules["magic"] = fake
    yield
    if old is not None:
        sys.modules["magic"] = old
    else:
        del sys.modules["magic"]


_MP3_HEADER = b"\xff\xfb\x90\x00" + b"\x00" * 256

_ID3_HEADER = (
    b"ID3"
    b"\x04\x00"
    b"\x00"
    b"\x00\x00\x02\x00"
    + b"\x00" * 256
    + b"\xff\xfb\x90\x00"
    + b"\x00" * 256
)

_JPEG_HEADER = (
    b"\xff\xd8\xff\xe0"
    b"\x00\x10JFIF\x00\x01\x01\x00"
    b"\x00\x01\x00\x01\x00\x00"
    + b"\x00" * 256
)

_PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01"
    b"\x00\x00\x00\x01"
    b"\x08\x02"
    b"\x00\x00\x00"
    b"\x90wS\xde"
    + b"\x00" * 256
)

_MP4_HEADER = (
    b"\x00\x00\x00\x20"
    b"ftypisom"
    b"\x00\x00\x02\x00"
    b"isomiso2mp41"
    + b"\x00" * 256
)

_WEBM_HEADER = (
    b"\x1a\x45\xdf\xa3"
    b"\x93\x42\x86\x81\x01"
    b"\x42\xf7\x81\x01"
    b"\x42\xf2\x81\x04"
    b"\x42\xf3\x81\x08"
    b"\x42\x82\x84webm"
    b"\x42\x87\x81\x04"
    b"\x42\x85\x81\x02"
    + b"\x00" * 256
)


class TestValidateAudio:
    def test_valid_mp3(self) -> None:
        result = validate_audio(_MP3_HEADER, "song.mp3")
        assert "audio" in result or "video" in result

    def test_valid_id3(self) -> None:
        result = validate_audio(_ID3_HEADER, "song.mp3")
        assert "audio" in result

    def test_image_as_audio(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_audio(_JPEG_HEADER, "fake.mp3")
        assert exc.value.status_code == 415

    def test_dangerous_extension(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_audio(_MP3_HEADER, "song.mp3.exe")
        assert exc.value.status_code == 415

    def test_empty_data(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_audio(b"", "empty.mp3")
        assert exc.value.status_code == 415


class TestMimeFromSignatures:
    def test_jpeg_png_webp(self) -> None:
        assert _mime_from_signatures(_JPEG_HEADER) == "image/jpeg"
        assert _mime_from_signatures(_PNG_HEADER) == "image/png"

    def test_webp_riff(self) -> None:
        webp = (
            b"RIFF"
            + (40).to_bytes(4, "little")
            + b"WEBP"
            + b"VP8 "
            + b"\x00" * 32
        )
        assert _mime_from_signatures(webp) == "image/webp"


class TestValidateImage:
    def test_valid_jpeg(self) -> None:
        result = validate_image(_JPEG_HEADER, "cover.jpg")
        assert result == "image/jpeg"

    def test_valid_jpeg_when_magic_unavailable(self) -> None:
        with patch(
            "app.services.file_validator._mime_with_magic",
            return_value=None,
        ):
            result = validate_image(_JPEG_HEADER, "cover.jpg")
            assert result == "image/jpeg"

    def test_valid_png(self) -> None:
        result = validate_image(_PNG_HEADER, "cover.png")
        assert result == "image/png"

    def test_audio_as_image(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_image(_MP3_HEADER, "fake.png")
        assert exc.value.status_code == 415

    def test_dangerous_extension(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_image(_JPEG_HEADER, "img.jpg.exe")
        assert exc.value.status_code == 415


class TestValidateVideo:
    def test_valid_mp4(self) -> None:
        result = validate_video(_MP4_HEADER, "clip.mp4")
        assert "video" in result

    def test_valid_webm(self) -> None:
        result = validate_video(_WEBM_HEADER, "clip.webm")
        assert "video" in result or "matroska" in result

    def test_audio_as_video(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_video(_MP3_HEADER, "fake.mp4")
        assert exc.value.status_code == 415

    def test_dangerous_extension(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_video(_MP4_HEADER, "vid.mp4.bat")
        assert exc.value.status_code == 415


_SCAN_MOD = "app.services.scan_service"


class TestScanForMalware:
    async def test_clean_passes_through(self) -> None:
        clean = ScanResult(verdict=ScanVerdict.CLEAN)
        with patch(
            f"{_SCAN_MOD}.scan_bytes",
            new_callable=AsyncMock,
            return_value=clean,
        ):
            await scan_for_malware(b"safe", "track.mp3")

    async def test_skipped_passes_through(self) -> None:
        skipped = ScanResult(verdict=ScanVerdict.SKIPPED)
        with patch(
            f"{_SCAN_MOD}.scan_bytes",
            new_callable=AsyncMock,
            return_value=skipped,
        ):
            await scan_for_malware(b"data", "track.mp3")

    async def test_infected_raises_422(self) -> None:
        infected = ScanResult(
            verdict=ScanVerdict.INFECTED, detail="Eicar-Test"
        )
        with (
            patch(
                f"{_SCAN_MOD}.scan_bytes",
                new_callable=AsyncMock,
                return_value=infected,
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await scan_for_malware(b"bad", "malware.mp3")
        assert exc.value.status_code == 422

    async def test_error_fail_closed_raises_503(self) -> None:
        error = ScanResult(
            verdict=ScanVerdict.ERROR, detail="clamd down"
        )
        with (
            patch(
                f"{_SCAN_MOD}.scan_bytes",
                new_callable=AsyncMock,
                return_value=error,
            ),
            patch(
                "dotsound_private_core.services.upload_policy"
                ".should_reject_on_av_error",
                return_value=True,
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await scan_for_malware(b"data", "track.mp3")
        assert exc.value.status_code == 503

    async def test_error_fail_open_passes(self) -> None:
        error = ScanResult(
            verdict=ScanVerdict.ERROR, detail="clamd down"
        )
        with (
            patch(
                f"{_SCAN_MOD}.scan_bytes",
                new_callable=AsyncMock,
                return_value=error,
            ),
            patch(
                "dotsound_private_core.services.upload_policy"
                ".should_reject_on_av_error",
                return_value=False,
            ),
        ):
            await scan_for_malware(b"data", "track.mp3")
