from __future__ import annotations

import structlog
from elasticsearch import AsyncElasticsearch

from app.config import settings

logger = structlog.get_logger(__name__)

_TRACKS_MAPPING = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "track_id": {"type": "integer"},
            "title": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256,
                    }
                },
            },
            "title_sayt": {
                "type": "search_as_you_type",
                "max_shingle_size": 3,
            },
            "artist": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256,
                    }
                },
            },
            "artist_sayt": {
                "type": "search_as_you_type",
                "max_shingle_size": 3,
            },
            "title_translit": {
                "type": "search_as_you_type",
                "max_shingle_size": 3,
            },
            "artist_translit": {
                "type": "search_as_you_type",
                "max_shingle_size": 3,
            },
            "genre": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 100,
                    }
                },
            },
            "play_count": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "is_public": {"type": "boolean"},
            "playable": {"type": "boolean"},
        }
    },
}

_ARTISTS_MAPPING = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "artist_id": {"type": "integer"},
            "name": {"type": "text"},
            "name_sayt": {"type": "search_as_you_type", "max_shingle_size": 3},
            "name_translit": {
                "type": "search_as_you_type",
                "max_shingle_size": 3,
            },
            "name_normalized": {
                "type": "keyword",
            },
            "soundcloud_permalink": {"type": "text"},
        }
    },
}


async def ensure_index_exists(
    es: AsyncElasticsearch, index_name: str, mapping: dict
) -> None:
    exists = await es.indices.exists(index=index_name)
    if not exists:
        await es.indices.create(
            index=index_name,
            settings=mapping["settings"],
            mappings=mapping["mappings"],
        )
        logger.info("elasticsearch_index_created", index=index_name)
    else:
        # Additive mapping update — safe for new fields, no downtime.
        try:
            await es.indices.put_mapping(
                index=index_name,
                body={"properties": mapping["mappings"]["properties"]},
            )
            logger.debug("elasticsearch_mapping_updated", index=index_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "elasticsearch_mapping_update_failed",
                index=index_name,
                error=str(exc),
            )


async def ensure_tracks_artist_indices(es: AsyncElasticsearch) -> None:
    await ensure_index_exists(
        es, settings.elasticsearch_index_tracks, _TRACKS_MAPPING
    )
    await ensure_index_exists(
        es, settings.elasticsearch_index_artists, _ARTISTS_MAPPING
    )


async def wait_for_cluster(
    es: AsyncElasticsearch, timeout: float = 30.0
) -> str | None:
    try:
        h = await es.cluster.health(
            wait_for_status="yellow", timeout=f"{int(timeout)}s"
        )
        return str(h.get("status"))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "elasticsearch_cluster_wait_failed",
            error=str(exc),
        )
        return None
