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
    """Upload audio bytes to MinIO; return the object file_key."""
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
    """Generate a presigned GET URL valid for 1 hour."""
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


_ALLOWED_COVER_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_COVER_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


async def upload_cover(
    data: bytes,
    content_type: str,
    user_id: int | None = None,
) -> str:
    """Upload cover image bytes to MinIO; return file_key."""
    ext = _COVER_EXT_MAP.get(content_type, "jpg")
    prefix = str(user_id) if user_id else "anon"
    file_key = f"covers/{prefix}/{uuid.uuid4().hex}.{ext}"

    logger.info(
        "s3_cover_upload_started",
        file_key=file_key,
        size_bytes=len(data),
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=file_key,
            Body=data,
            ContentType=content_type,
        )
    logger.info("s3_cover_upload_completed", file_key=file_key)
    return file_key


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
    ext = _COVER_EXT_MAP.get(content_type, "jpg")
    file_key = f"avatars/{user_id}/{uuid.uuid4().hex}.{ext}"
    logger.info(
        "s3_avatar_upload_started",
        file_key=file_key,
        size_bytes=len(data),
    )
    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=file_key,
            Body=data,
            ContentType=content_type,
        )
    logger.info("s3_avatar_upload_completed", file_key=file_key)
    return file_key


async def stream_object_range(
    file_key: str,
    range_header: str | None = None,
) -> tuple[Any, int, str | None, str]:
    """Fetch (a range of) an S3 object for streaming.

    Returns (body, content_length, content_range, content_type).
    Raises ClientError if the key does not exist.
    """
    kwargs: dict[str, Any] = {
        "Bucket": settings.minio_bucket,
        "Key": file_key,
    }
    if range_header:
        kwargs["Range"] = range_header
    logger.debug(
        "s3_stream_range_requested",
        file_key=file_key,
        range=range_header,
    )
    async with get_s3_client() as s3:
        try:
            response = await s3.get_object(**kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            logger.warning(
                "s3_stream_range_error", file_key=file_key, code=code
            )
            raise
        return (
            response["Body"],
            int(response["ContentLength"]),
            response.get("ContentRange"),
            response.get("ContentType", "audio/mpeg"),
        )


async def ensure_bucket_exists() -> None:
    """Create the audio bucket if it doesn't exist yet."""
    async with get_s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=settings.minio_bucket)
            logger.debug(
                "s3_bucket_exists", bucket=settings.minio_bucket
            )
        except Exception:
            await s3.create_bucket(Bucket=settings.minio_bucket)
            logger.info(
                "s3_bucket_created", bucket=settings.minio_bucket
            )
