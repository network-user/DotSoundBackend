from __future__ import annotations

import structlog
from dataclasses import dataclass

from app.config import settings
from app.search.es_client import es_available, get_es

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SearchTrackHit:
    track_id: int
    score: float | None = None


@dataclass(frozen=True, slots=True)
class SuggestItem:
    kind: str
    id: int
    title: str | None
    name: str | None


def _base_track_filters(
    *, playable_only: bool
) -> list[dict]:
    filters: list[dict] = [
        {"term": {"is_active": True}},
        {"term": {"is_public": True}},
    ]
    if playable_only:
        filters.append({"term": {"playable": True}})
    return filters


async def es_search_tracks(
    q: str,
    *,
    page: int,
    size: int,
    playable_only: bool,
) -> tuple[list[int], int] | None:
    if not es_available():
        return None
    if not (q or "").strip():
        return None
    es = get_es()
    offset = (page - 1) * size
    must = {
        "multi_match": {
            "query": q.strip(),
            "type": "best_fields",
            "fields": [
                "title^2",
                "artist^2",
                "title_sayt^1.2",
                "artist_sayt^1.2",
                "genre",
            ],
            "fuzziness": "AUTO",
        }
    }
    body: dict = {
        "query": {
            "bool": {
                "filter": _base_track_filters(
                    playable_only=playable_only
                ),
                "must": [must],
            }
        },
        "from": offset,
        "size": size,
        "track_total_hits": True,
        "sort": [
            "_score",
            {"play_count": "desc"},
        ],
    }
    try:
        res = await es.search(
            index=settings.elasticsearch_index_tracks, body=body
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_search_tracks_failed", error=str(exc))
        return None
    total = 0
    th = res.get("hits", {}).get("total", 0)
    if isinstance(th, dict):
        total = int(th.get("value", 0))
    else:
        total = int(th)
    hits = res.get("hits", {}).get("hits", [])
    ids: list[int] = []
    for h in hits:
        src = h.get("_source") or {}
        tid = src.get("track_id")
        if tid is None and h.get("_id"):
            try:
                tid = int(h["_id"])
            except (TypeError, ValueError):
                continue
        if tid is not None:
            ids.append(int(tid))
    return ids, total


async def es_suggest_mixed(
    q: str,
    *,
    limit: int = 8,
) -> list[SuggestItem] | None:
    if not es_available():
        return None
    if not (q or "").strip():
        return None
    es = get_es()
    qstrip = q.strip()
    per = max(1, min(8, limit // 2 + 1))
    t_body = {
        "query": {
            "bool": {
                "filter": _base_track_filters(playable_only=False),
                "must": [
                    {
                        "multi_match": {
                            "query": qstrip,
                            "type": "bool_prefix",
                            "fields": [
                                "title_sayt",
                                "title_sayt._2gram",
                                "title_sayt._3gram",
                                "artist_sayt",
                                "artist_sayt._2gram",
                                "artist_sayt._3gram",
                            ],
                        }
                    }
                ],
            }
        },
        "size": per,
        "sort": [
            {"play_count": "desc"},
        ],
    }
    a_body = {
        "query": {
            "multi_match": {
                "query": qstrip,
                "type": "bool_prefix",
                "fields": [
                    "name_sayt",
                    "name_sayt._2gram",
                    "name_sayt._3gram",
                    "name",
                ],
            }
        },
        "size": per,
    }
    try:
        t_res, a_res = await es.search(
            index=settings.elasticsearch_index_tracks, body=t_body
        ), await es.search(
            index=settings.elasticsearch_index_artists, body=a_body
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_suggest_failed", error=str(exc))
        return None
    out: list[SuggestItem] = []
    for h in t_res.get("hits", {}).get("hits", []):
        src = h.get("_source") or {}
        tid = src.get("track_id")
        if tid is None:
            continue
        out.append(
            SuggestItem(
                kind="track",
                id=int(tid),
                title=src.get("title"),
                name=src.get("artist"),
            )
        )
    for h in a_res.get("hits", {}).get("hits", []):
        src = h.get("_source") or {}
        aid = src.get("artist_id")
        if aid is None:
            continue
        out.append(
            SuggestItem(
                kind="artist",
                id=int(aid),
                title=None,
                name=src.get("name"),
            )
        )
    return out[:limit]
