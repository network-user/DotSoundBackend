from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.track import Track
from app.search.es_client import es_available, get_es
from app.search.translit import transliterate

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
    cover_key: str | None = None
    duration_seconds: int | None = None


def _base_track_filters(*, playable_only: bool) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"term": {"is_active": True}},
        {"term": {"is_public": True}},
    ]
    if playable_only:
        filters.append({"term": {"playable": True}})
    return filters


def _track_multi_match_fields() -> list[str]:
    return [
        "title^2",
        "artist^2",
        "title_sayt^1.2",
        "artist_sayt^1.2",
        "title_translit^1.5",
        "artist_translit^1.5",
        "genre",
    ]


def _track_search_should_clauses(
    q_text: str,
) -> list[dict[str, Any]]:
    fields = _track_multi_match_fields()
    fuzz = settings.elasticsearch_track_fuzziness
    fmax = settings.elasticsearch_fuzzy_max_expansions
    clauses: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": q_text,
                "type": "best_fields",
                "fields": fields,
                "boost": 1.0,
            }
        },
        {
            "multi_match": {
                "query": q_text,
                "type": "best_fields",
                "fields": fields,
                "fuzziness": fuzz,
                "fuzzy_max_expansions": fmax,
                "boost": 0.35,
            }
        },
    ]
    q_translit = transliterate(q_text)
    if q_translit and q_translit != q_text:
        clauses.append(
            {
                "multi_match": {
                    "query": q_translit,
                    "type": "best_fields",
                    "fields": fields,
                    "boost": 0.8,
                }
            }
        )
    return clauses


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
    q_text = q.strip()
    body: dict[str, Any] = {
        "query": {
            "bool": {
                "filter": _base_track_filters(playable_only=playable_only),
                "should": _track_search_should_clauses(q_text),
                "minimum_should_match": 1,
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
    total = int(th.get("value", 0)) if isinstance(th, dict) else int(th)
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
    fuzz = settings.elasticsearch_track_fuzziness
    fmax = settings.elasticsearch_fuzzy_max_expansions
    q_translit = transliterate(qstrip)
    t_should: list[dict[str, Any]] = [
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
                    "title_translit",
                    "title_translit._2gram",
                    "artist_translit",
                    "artist_translit._2gram",
                ],
                "boost": 1.0,
            }
        },
        {
            "multi_match": {
                "query": qstrip,
                "type": "best_fields",
                "fields": ["title^2", "artist^2", "title_translit^1.5", "artist_translit^1.5"],
                "fuzziness": fuzz,
                "fuzzy_max_expansions": fmax,
                "boost": 0.25,
            }
        },
    ]
    if q_translit and q_translit != qstrip:
        t_should.append(
            {
                "multi_match": {
                    "query": q_translit,
                    "type": "bool_prefix",
                    "fields": [
                        "title_sayt",
                        "title_sayt._2gram",
                        "artist_sayt",
                        "artist_sayt._2gram",
                        "title_translit",
                        "artist_translit",
                    ],
                    "boost": 0.8,
                }
            }
        )
    t_body: dict[str, Any] = {
        "query": {
            "bool": {
                "filter": _base_track_filters(playable_only=False),
                "should": t_should,
                "minimum_should_match": 1,
            }
        },
        "size": per,
        "sort": [
            {"play_count": "desc"},
        ],
    }
    a_should: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": qstrip,
                "type": "bool_prefix",
                "fields": [
                    "name_sayt",
                    "name_sayt._2gram",
                    "name_sayt._3gram",
                    "name_translit",
                    "name_translit._2gram",
                    "name",
                    "soundcloud_permalink",
                ],
                "boost": 1.0,
            }
        },
        {
            "multi_match": {
                "query": qstrip,
                "type": "best_fields",
                "fields": [
                    "name^2",
                    "name_translit^1.5",
                    "soundcloud_permalink",
                ],
                "fuzziness": fuzz,
                "fuzzy_max_expansions": fmax,
                "boost": 0.25,
            }
        },
    ]
    if q_translit and q_translit != qstrip:
        a_should.append(
            {
                "multi_match": {
                    "query": q_translit,
                    "type": "bool_prefix",
                    "fields": [
                        "name_sayt",
                        "name_sayt._2gram",
                        "name_translit",
                    ],
                    "boost": 0.8,
                }
            }
        )
    a_body: dict[str, Any] = {
        "query": {
            "bool": {
                "should": a_should,
                "minimum_should_match": 1,
            }
        },
        "size": per,
    }
    try:
        t_res = await es.search(
            index=settings.elasticsearch_index_tracks, body=t_body
        )
        a_res = await es.search(
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
                cover_key=None,
                duration_seconds=None,
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
                cover_key=None,
                duration_seconds=None,
            )
        )
    return out[:limit]


async def enrich_suggest_tracks_from_db(
    session: AsyncSession, items: list[SuggestItem]
) -> list[SuggestItem]:
    """Attach cover and duration for track rows from PostgreSQL."""
    tids = [i.id for i in items if i.kind == "track"]
    if not tids:
        return items
    r = await session.execute(
        select(Track.id, Track.cover_key, Track.duration_seconds).where(
            Track.id.in_(tids)
        )
    )
    meta: dict[int, tuple[str | None, int | None]] = {
        int(row[0]): (row[1], row[2]) for row in r.all()
    }
    out: list[SuggestItem] = []
    for i in items:
        if i.kind != "track":
            out.append(i)
            continue
        ck, dur = meta.get(i.id, (None, None))
        out.append(
            SuggestItem(
                kind=i.kind,
                id=i.id,
                title=i.title,
                name=i.name,
                cover_key=ck,
                duration_seconds=dur,
            )
        )
    return out


async def es_search_artists(q: str, *, limit: int = 20) -> list[int] | None:
    if not es_available():
        return None
    if not (q or "").strip():
        return None
    es = get_es()
    q_text = q.strip()
    artist_fields = [
        "name^2",
        "name_sayt^1.2",
        "name_sayt._2gram",
        "name_translit^1.5",
        "soundcloud_permalink^1.3",
    ]
    fuzz = settings.elasticsearch_track_fuzziness
    fmax = settings.elasticsearch_fuzzy_max_expansions
    q_translit = transliterate(q_text)
    artist_should: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": q_text,
                "type": "best_fields",
                "fields": artist_fields,
                "boost": 1.0,
            }
        },
        {
            "multi_match": {
                "query": q_text,
                "type": "best_fields",
                "fields": artist_fields,
                "fuzziness": fuzz,
                "fuzzy_max_expansions": fmax,
                "boost": 0.35,
            }
        },
    ]
    if q_translit and q_translit != q_text:
        artist_should.append(
            {
                "multi_match": {
                    "query": q_translit,
                    "type": "best_fields",
                    "fields": artist_fields,
                    "boost": 0.8,
                }
            }
        )
    body: dict[str, Any] = {
        "query": {
            "bool": {
                "should": artist_should,
                "minimum_should_match": 1,
            }
        },
        "size": min(100, max(1, limit)),
        "track_total_hits": False,
    }
    try:
        res = await es.search(
            index=settings.elasticsearch_index_artists, body=body
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_search_artists_failed", error=str(exc))
        return None
    out: list[int] = []
    for h in res.get("hits", {}).get("hits", []):
        src = h.get("_source") or {}
        aid = src.get("artist_id")
        if aid is not None:
            out.append(int(aid))
    return out
