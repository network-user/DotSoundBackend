import mimetypes

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ALLOWED_AUDIO_MIMES = frozenset(
    {
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/flac",
        "audio/mp4",
        "audio/x-m4a",
        "audio/aac",
    }
)
_ALLOWED_COVER_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_AUDIO_BYTES = 50 * 1024 * 1024
_MAX_COVER_BYTES = 5 * 1024 * 1024


def _resolve_mime(file: UploadFile) -> str:
    mime = file.content_type or ""
    if not mime or mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime = guessed or mime
    return mime


def _audio_extension(mime: str) -> str:
    _map = {
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/flac": "flac",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/aac": "aac",
    }
    return _map.get(mime, "bin")


class UploadService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TrackRepository(session)

    async def upload_track(
        self,
        file: UploadFile,
        title: str,
        artist: str | None,
        cover: UploadFile | None = None,
        uploader_id: int | None = None,
        is_public: bool = True,
    ) -> Track:
        mime = _resolve_mime(file)
        logger.info(
            "upload_validation",
            filename=file.filename,
            mime=mime,
            uploader_id=uploader_id,
        )

        if mime not in _ALLOWED_AUDIO_MIMES:
            logger.warning("upload_rejected_mime", mime=mime)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported audio format: {mime}",
            )

        data = await file.read()
        if len(data) > _MAX_AUDIO_BYTES:
            logger.warning(
                "upload_rejected_size", size_bytes=len(data)
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio file exceeds 50 MB limit",
            )

        ext = _audio_extension(mime)
        file_key = await s3.upload_audio(
            data=data,
            extension=ext,
            content_type=mime,
            user_id=uploader_id,
        )

        cover_key: str | None = None
        if cover and cover.filename:
            cover_key = await self._upload_cover(
                cover, uploader_id
            )

        track = await self._repo.create(
            title=title,
            artist=artist,
            file_key=file_key,
            cover_key=cover_key,
            uploaded_by_id=uploader_id,
            is_public=is_public,
        )
        logger.info(
            "upload_complete",
            track_id=track.id,
            file_key=file_key,
            has_cover=cover_key is not None,
        )
        return track

    async def _upload_cover(
        self,
        cover: UploadFile,
        user_id: int | None,
    ) -> str | None:
        mime = _resolve_mime(cover)
        if mime not in _ALLOWED_COVER_MIMES:
            logger.warning(
                "cover_rejected_mime", mime=mime
            )
            return None

        data = await cover.read()
        if len(data) > _MAX_COVER_BYTES:
            logger.warning(
                "cover_rejected_size", size_bytes=len(data)
            )
            return None

        return await s3.upload_cover(
            data=data, content_type=mime, user_id=user_id
        )
