from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artist import Artist, TrackArtist
from app.models.track import Track
from app.search.documents import artist_to_doc, track_to_doc
from app.search.es_client import es_available, get_es
from app.search.indices import ensure_tracks_artist_indices, wait_for_cluster

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _indexable_track(t: Track) -> bool:
    return bool(t.is_active) and bool(t.is_public)


async def index_track_document(session: AsyncSession, t: Track) -> None:
    if not es_available():
        return
    es = get_es()
    idx = settings.elasticsearch_index_tracks
    tid = str(t.id)
    if not _indexable_track(t):
        try:
            await es.delete(
                index=idx, id=tid, ignore=[400, 404]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "es_delete_track_failed", track_id=t.id, error=str(exc)
            )
        return
    try:
        await es.index(
            index=idx,
            id=tid,
            document=track_to_doc(t),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "es_index_track_failed", track_id=t.id, error=str(exc)
        )


async def index_artist_document(
    session: AsyncSession, artist_id: int
) -> None:
    if not es_available():
        return
    a = await session.get(Artist, artist_id)
    if not a:
        return await delete_artist_document(artist_id)
    es = get_es()
    idx = settings.elasticsearch_index_artists
    try:
        await es.index(
            index=idx,
            id=str(artist_id),
            document=artist_to_doc(a),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "es_index_artist_failed",
            artist_id=artist_id,
            error=str(exc),
        )


async def delete_track_document(track_id: int) -> None:
    if not es_available():
        return
    try:
        await get_es().delete(
            index=settings.elasticsearch_index_tracks,
            id=str(track_id),
            ignore=[400, 404],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "es_delete_track_failed", track_id=track_id, error=str(exc)
        )


async def delete_artist_document(artist_id: int) -> None:
    if not es_available():
        return
    try:
        await get_es().delete(
            index=settings.elasticsearch_index_artists,
            id=str(artist_id),
            ignore=[400, 404],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "es_delete_artist_failed",
            artist_id=artist_id,
            error=str(exc),
        )


async def count_tracks_indexed() -> int:
    if not es_available():
        return 0
    es = get_es()
    r = await es.count(
        index=settings.elasticsearch_index_tracks, ignore_unavailable=True
    )
    n = r.get("count", 0)
    return int(n) if n is not None else 0


async def init_elasticsearch_starter() -> None:
    if not es_available():
        return
    es = get_es()
    try:
        await wait_for_cluster(es, timeout=25.0)
        await ensure_tracks_artist_indices(es)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "elasticsearch_bootstrap_failed", error=str(exc)
        )


async def reindex_all_tracks_artist_backfill() -> int:
    """Reindex all artists then all public active tracks. Returns n tracks."""
    if not es_available():
        return 0
    from app.core.db import AsyncSessionLocal

    await init_elasticsearch_starter()
    n_tracks = 0
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Artist.id).order_by(Artist.id)
        )
        a_ids = [row[0] for row in res.all()]
        for aid in a_ids:
            await index_artist_document(session, int(aid))

        res2 = await session.execute(
            select(Track).where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
            )
        )
        tracks = list(res2.scalars().all())
        n_tracks = len(tracks)
        for t in tracks:
            await index_track_document(session, t)
        await session.commit()
    logger.info("es_reindex_backfill_done", track_count=n_tracks)
    return n_tracks


async def reindex_artist_affected_tracks(artist_id: int) -> None:
    """Reindex tracks linked to an artist (Track.artist may be stale)."""
    if not es_available():
        return
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TrackArtist.track_id)
            .where(TrackArtist.artist_id == artist_id)
        )
        ids = [int(row[0]) for row in res.all()]
        for tid in ids:
            t = await session.get(Track, tid)
            if t:
                await index_track_document(session, t)
        await session.commit()
