from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.artist import Artist
from app.models.track import Track
from app.services import compute_queue_service as q

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

JOB_TYPE_ARG = "job_type"


def _parse_since(
    s: str | None,
) -> datetime | None:
    if not s or not s.strip():
        return None
    d = date.fromisoformat(s.strip())
    return datetime(
        d.year,
        d.month,
        d.day,
        tzinfo=UTC,
    )


async def _backfill_tracks(
    session: AsyncSession,
    *,
    job_kind: str,
    limit: int,
    since: datetime | None,
    priority: int,
    feature_version: str,
    dry_run: bool,
) -> dict[str, int]:
    stmt = select(Track.id)
    if since is not None:
        stmt = stmt.where(Track.created_at >= since)
    stmt = stmt.order_by(Track.id.asc()).limit(limit)
    tids = [
        row[0]
        for row in (await session.execute(stmt)).all()
    ]
    enq = 0
    skip_inel = 0
    skip_dup = 0
    for tid in tids:
        tr = await session.get(Track, tid)
        if tr is None:
            skip_inel += 1
            continue
        if job_kind == q.JOB_TRACK_AUDIO_FEATURES and tr.file_key is None:
            skip_inel += 1
            continue
        existing = await q.find_existing_job(
            session,
            job_type=job_kind,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=tid,
            feature_version=feature_version,
        )
        if existing is not None:
            skip_dup += 1
            continue
        if dry_run:
            enq += 1
            continue
        if job_kind == q.JOB_TRACK_AUDIO_FEATURES:
            await q.enqueue_track_audio_features(
                session,
                track_id=tid,
                feature_version=feature_version,
                priority=priority,
            )
        else:
            await q.enqueue_catalog_ingest_normalize(
                session,
                track_id=tid,
                feature_version=feature_version,
                priority=priority,
            )
        enq += 1
    if not dry_run:
        await session.commit()
    return {
        "enqueued": enq,
        "skipped_ineligible": skip_inel,
        "skipped_duplicate": skip_dup,
    }


async def _backfill_artists(
    session: AsyncSession,
    *,
    limit: int,
    since: datetime | None,
    priority: int,
    feature_version: str,
    dry_run: bool,
) -> dict[str, int]:
    stmt = select(Artist.id)
    if since is not None:
        stmt = stmt.where(Artist.created_at >= since)
    stmt = stmt.order_by(Artist.id.asc()).limit(limit)
    aids = [
        row[0]
        for row in (await session.execute(stmt)).all()
    ]
    enq = 0
    skip_dup = 0
    for aid in aids:
        existing = await q.find_existing_job(
            session,
            job_type=q.JOB_ARTIST_FEATURES_UPDATE,
            target_kind=q.TARGET_KIND_ARTIST,
            target_id=aid,
            feature_version=feature_version,
        )
        if existing is not None:
            skip_dup += 1
            continue
        if dry_run:
            enq += 1
            continue
        await q.enqueue_artist_features(
            session,
            artist_id=aid,
            feature_version=feature_version,
            priority=priority,
        )
        enq += 1
    if not dry_run:
        await session.commit()
    return {
        "enqueued": enq,
        "skipped_ineligible": 0,
        "skipped_duplicate": skip_dup,
    }


async def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Enqueue compute jobs for backfill.",
    )
    p.add_argument(
        "--type",
        dest=JOB_TYPE_ARG,
        required=True,
        choices=[
            q.JOB_TRACK_AUDIO_FEATURES,
            q.JOB_CATALOG_INGEST_NORMALIZE,
            q.JOB_ARTIST_FEATURES_UPDATE,
        ],
    )
    p.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    p.add_argument(
        "--priority",
        type=int,
        default=0,
    )
    p.add_argument(
        "--since",
        type=str,
        default=None,
    )
    p.add_argument(
        "--feature-version",
        type=str,
        default=q.DEFAULT_FEATURE_VERSION,
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
    )
    args = p.parse_args(argv)
    since = _parse_since(args.since)
    jt: str = getattr(
        args,
        JOB_TYPE_ARG,
    )
    fr = str(args.feature_version)
    pr = int(args.priority)
    lim = int(args.limit)
    dr = bool(args.dry_run)

    async with AsyncSessionLocal() as session:
        if jt in (
            q.JOB_TRACK_AUDIO_FEATURES,
            q.JOB_CATALOG_INGEST_NORMALIZE,
        ):
            st = await _backfill_tracks(
                session,
                job_kind=jt,
                limit=lim,
                since=since,
                priority=pr,
                feature_version=fr,
                dry_run=dr,
            )
        else:
            st = await _backfill_artists(
                session,
                limit=lim,
                since=since,
                priority=pr,
                feature_version=fr,
                dry_run=dr,
            )
    logger.info("compute_backfill_done", **st, type=jt)
    print(
        f"type={jt} enqueued={st['enqueued']} "
        f"skipped_ineligible={st['skipped_ineligible']} "
        f"skipped_duplicate={st['skipped_duplicate']}"
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
