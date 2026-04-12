import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
import structlog
from botocore.exceptions import ClientError

from app.config import settings

_session = aioboto3.Session()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PRESIGNED_TTL_SECONDS = 3600

_ALLOWED_COVER_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_COVER_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator[Any, None]:
    protocol = "https" if settings.minio_use_ssl else "http"
    endpoint = f"{protocol}://{settings.minio_endpoint}"
    async with _session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    ) as client:
        yield client


async def upload_audio(
    data: bytes,
    extension: str,
    content_type: str,
    user_id: int | None = None,
) -> str:
    prefix = str(user_id) if user_id else "anon"
    file_key = f"{prefix}/{uuid.uuid4().hex}.{extension}"

    logger.info(
        "s3_upload_started",
        file_key=file_key,
        content_type=content_type,
        size_bytes=len(data),
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=file_key,
            Body=data,
            ContentType=content_type,
        )
    logger.info("s3_upload_completed", file_key=file_key)
    return file_key


async def get_presigned_url(file_key: str) -> str:
    logger.debug("s3_presign_requested", file_key=file_key)
    async with get_s3_client() as s3:
        url: str = await s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.minio_bucket,
                "Key": file_key,
            },
            ExpiresIn=_PRESIGNED_TTL_SECONDS,
        )
    logger.debug("s3_presign_generated", file_key=file_key)
    return url


async def upload_image(
    data: bytes,
    prefix: str,
    max_size: int | None = None,
    user_id: int | None = None,
) -> tuple[str, str, int, int]:
    from app.services.media_service import (
        process_image,
    )

    processed, thumb, w, h = process_image(
        data, max_size
    )

    owner = str(user_id) if user_id else "anon"
    base = f"{prefix}/{owner}/{uuid.uuid4().hex}"
    img_key = f"{base}.webp"
    thumb_key = f"{base}_thumb.webp"

    logger.info(
        "s3_image_upload_started",
        img_key=img_key,
        original_bytes=len(data),
        processed_bytes=len(processed),
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=img_key,
            Body=processed,
            ContentType="image/webp",
        )
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=thumb_key,
            Body=thumb,
            ContentType="image/webp",
        )
    logger.info(
        "s3_image_upload_completed",
        img_key=img_key,
    )
    return img_key, thumb_key, w, h


async def upload_cover(
    data: bytes,
    content_type: str,
    user_id: int | None = None,
) -> str:
    img_key, _, _, _ = await upload_image(
        data,
        prefix="covers",
        max_size=settings.image_cover_max_size,
        user_id=user_id,
    )
    return img_key


async def upload_voice(
    data: bytes,
    user_id: int | None = None,
) -> tuple[str, int, list[float]]:
    from app.services.media_service import (
        process_voice,
    )

    ogg_data, duration, waveform = (
        await process_voice(data)
    )

    owner = str(user_id) if user_id else "anon"
    file_key = (
        f"voice/{owner}/{uuid.uuid4().hex}.ogg"
    )
    logger.info(
        "s3_voice_upload_started",
        file_key=file_key,
        duration=duration,
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=file_key,
            Body=ogg_data,
            ContentType="audio/ogg",
        )
    logger.info(
        "s3_voice_upload_completed",
        file_key=file_key,
    )
    return file_key, duration, waveform


async def delete_object(file_key: str) -> None:
    logger.info("s3_delete_started", file_key=file_key)
    async with get_s3_client() as s3:
        await s3.delete_object(
            Bucket=settings.minio_bucket, Key=file_key
        )
    logger.info("s3_delete_completed", file_key=file_key)


async def upload_avatar(
    data: bytes,
    content_type: str,
    user_id: int,
) -> str:
    img_key, _, _, _ = await upload_image(
        data,
        prefix="avatars",
        max_size=settings.image_avatar_max_size,
        user_id=user_id,
    )
    return img_key


async def download_object_range(
    file_key: str,
    range_header: str | None = None,
) -> tuple[bytes, int, str | None, str]:
    """Download (a range of) an S3 object.

    Returns (data, content_length, content_range, content_type).
    All data is read inside the S3 client context to avoid
    connection-closed errors.
    """
    kwargs: dict[str, Any] = {
        "Bucket": settings.minio_bucket,
        "Key": file_key,
    }
    if range_header:
        kwargs["Range"] = range_header
    logger.debug(
        "s3_range_requested",
        file_key=file_key,
        range=range_header,
    )
    async with get_s3_client() as s3:
        try:
            response = await s3.get_object(
                **kwargs
            )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            logger.warning(
                "s3_range_error",
                file_key=file_key,
                code=code,
            )
            raise
        async with response["Body"] as stream:
            data: bytes = await stream.read()
        return (
            data,
            int(response["ContentLength"]),
            response.get("ContentRange"),
            response.get(
                "ContentType", "audio/mpeg"
            ),
        )


async def download_object(file_key: str) -> bytes:
    logger.debug("s3_download_requested", file_key=file_key)
    async with get_s3_client() as s3:
        response = await s3.get_object(
            Bucket=settings.minio_bucket, Key=file_key
        )
        async with response["Body"] as stream:
            data: bytes = await stream.read()
    logger.debug("s3_download_complete", file_key=file_key)
    return data


async def upload_object(
    key: str, data: bytes, content_type: str
) -> None:
    logger.debug(
        "s3_upload_object_started",
        key=key,
        size_bytes=len(data),
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    logger.debug("s3_upload_object_complete", key=key)


_BUCKET_RETRY_ATTEMPTS = 5
_BUCKET_RETRY_DELAY = 2.0


async def ensure_bucket_exists() -> None:
    """Create the audio bucket if it doesn't exist yet.

    Retries on connection errors because MinIO may still be starting.
    """
    for attempt in range(1, _BUCKET_RETRY_ATTEMPTS + 1):
        try:
            async with get_s3_client() as s3:
                try:
                    await s3.head_bucket(
                        Bucket=settings.minio_bucket
                    )
                    logger.debug(
                        "s3_bucket_exists",
                        bucket=settings.minio_bucket,
                    )
                    return
                except ClientError as exc:
                    code = exc.response["Error"]["Code"]
                    if code in ("404", "NoSuchBucket"):
                        await s3.create_bucket(
                            Bucket=settings.minio_bucket
                        )
                        logger.info(
                            "s3_bucket_created",
                            bucket=settings.minio_bucket,
                        )
                        return
                    raise
        except Exception as exc:
            if attempt == _BUCKET_RETRY_ATTEMPTS:
                logger.error(
                    "s3_bucket_check_failed",
                    attempt=attempt,
                    error=str(exc),
                )
                raise
            logger.warning(
                "s3_bucket_check_retry",
                attempt=attempt,
                error=str(exc),
                next_retry_in=_BUCKET_RETRY_DELAY * attempt,
            )
            await asyncio.sleep(_BUCKET_RETRY_DELAY * attempt)
