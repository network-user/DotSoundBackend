from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3

from app.config import settings

_session = aioboto3.Session()


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
