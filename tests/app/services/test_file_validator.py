import pytest
from fastapi import HTTPException

from app.services.file_validator import (
    validate_audio,
    validate_image,
    validate_video,
)


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


class TestValidateImage:
    def test_valid_jpeg(self) -> None:
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
