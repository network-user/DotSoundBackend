import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
import structlog

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
