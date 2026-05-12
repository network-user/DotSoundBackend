from __future__ import annotations

import structlog
from dotsound_private_core.services.upload_policy import (
    is_audio_mime_allowed,
    is_extension_dangerous,
    is_image_mime_allowed,
    is_video_mime_allowed,
)
from fastapi import HTTPException, status

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _mime_with_magic(data: bytes) -> str | None:
    try:
        import magic as _magic
    except ImportError:
        return None
    try:
        return _magic.from_buffer(data, mime=True)
    except Exception:
        logger.warning("magic_from_buffer_failed")
        return None


def _mime_from_signatures(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"fLaC":
        return "audio/flac"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if data[:3] == b"ID3":
        return "audio/mpeg"
    if data[:2] in (b"\xff\xf1", b"\xff\xf9"):
        return "audio/x-hx-aac-adts"
    if data[4:8] == b"ftyp":
        head = data[8:32]
        if b"mp4a" in head or b"M4A " in head:
            return "audio/mp4"
        return "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        if b"webm" in data[:256].lower():
            return "video/webm"
        return "video/x-matroska"
    return None


def _mime_with_pillow(data: bytes) -> str | None:
    from io import BytesIO

    from PIL import Image

    try:
        with Image.open(BytesIO(data)) as im:
            fmt = im.format
    except Exception:
        return None
    if fmt == "JPEG":
        return "image/jpeg"
    if fmt == "PNG":
        return "image/png"
    if fmt == "WEBP":
        return "image/webp"
    return None


def _detect_mime(data: bytes) -> str:
    if len(data) < 4:
        return "application/octet-stream"
    detected = _mime_with_magic(data)
    if detected is not None:
        return detected
    detected = _mime_from_signatures(data)
    if detected is not None:
        return detected
    detected = _mime_with_pillow(data)
    if detected is not None:
        return detected
    return "application/octet-stream"


def validate_audio(
    data: bytes,
    filename: str | None = None,
) -> str:
    if filename and is_extension_dangerous(filename):
        logger.warning(
            "upload_blocked_dangerous_ext",
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dangerous file extension detected",
        )
    detected = _detect_mime(data)
    if not is_audio_mime_allowed(detected):
        logger.warning(
            "upload_magic_mismatch",
            detected=detected,
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content is {detected}, not audio",
        )
    return detected


def validate_image(
    data: bytes,
    filename: str | None = None,
) -> str:
    if filename and is_extension_dangerous(filename):
        logger.warning(
            "upload_blocked_dangerous_ext",
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dangerous file extension detected",
        )
    detected = _detect_mime(data)
    if not is_image_mime_allowed(detected):
        logger.warning(
            "upload_magic_mismatch",
            detected=detected,
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content is {detected}, not image",
        )
    return detected


async def scan_for_malware(
    data: bytes,
    filename: str | None = None,
) -> None:
    from app.services.scan_service import ScanVerdict, scan_bytes

    result = await scan_bytes(data, filename or "")
    if result.verdict == ScanVerdict.INFECTED:
        logger.warning(
            "upload_malware_detected",
            filename=filename,
            detail=result.detail,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Malware detected in uploaded file",
        )
    if result.verdict == ScanVerdict.ERROR:
        from dotsound_private_core.services.upload_policy import (
            should_reject_on_av_error,
        )

        if should_reject_on_av_error():
            logger.warning(
                "upload_scan_error_fail_closed",
                filename=filename,
                detail=result.detail,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security scan unavailable",
            )


def validate_video(
    data: bytes,
    filename: str | None = None,
) -> str:
    if filename and is_extension_dangerous(filename):
        logger.warning(
            "upload_blocked_dangerous_ext",
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dangerous file extension detected",
        )
    detected = _detect_mime(data)
    if not is_video_mime_allowed(detected):
        logger.warning(
            "upload_magic_mismatch",
            detected=detected,
            filename=filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content is {detected}, not video",
        )
    return detected
