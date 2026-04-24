from __future__ import annotations

import structlog
from elasticsearch import AsyncElasticsearch

from app.config import settings

logger = structlog.get_logger(__name__)

_client: AsyncElasticsearch | None = None


def _es_configured() -> bool:
    return bool(
        settings.elasticsearch_enabled
        and (settings.elasticsearch_url or "").strip()
    )


def get_es() -> AsyncElasticsearch:
    global _client
    if not _es_configured():
        raise RuntimeError("Elasticsearch is not configured")
    if _client is None:
        _client = AsyncElasticsearch(
            settings.elasticsearch_url,
            request_timeout=30,
        )
    return _client


async def close_es() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("elasticsearch_client_closed")


def es_available() -> bool:
    return _es_configured()
