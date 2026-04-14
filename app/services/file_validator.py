from __future__ import annotations

import magic
import structlog
from fastapi import HTTPException, status

from dotsound_private_core.services.upload_policy import (
    is_audio_mime_allowed,
    is_extension_dangerous,
    is_image_mime_allowed,
    is_video_mime_allowed,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _detect_mime(data: bytes) -> str:
    if len(data) < 4:
        return "application/octet-stream"
    return magic.from_buffer(data, mime=True)


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
