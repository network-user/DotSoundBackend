"""Audit Track.hls_manifest_key against actual S3 objects.

Walks every track that the frontend would attempt to play via HLS
(public, internal-stream, active) and checks whether
``track.hls_manifest_key`` actually points to an existing
``master.m3u8`` in MinIO. Also flags tracks that *should* have HLS
(processing_status='active', file_key present, internal-stream)
but have a NULL ``hls_manifest_key`` -- those tracks fall back to
progressive forever and skew TT-canplay metrics.

Usage (from repo root):

    poetry run python scripts/audit_hls_manifests.py
    poetry run python scripts/audit_hls_manifests.py --limit 200
    poetry run python scripts/audit_hls_manifests.py --json

Read-only: never deletes or modifies anything. Safe to run against
production. Returns non-zero exit if any broken/missing manifest
keys are found, so CI can pick it up.

Requires DATABASE_URL and S3/MinIO env (``poetry install``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.db import (  # noqa: E402
    AsyncSessionLocal,
    dispose_engine,
)
from app.core.s3 import object_exists  # noqa: E402
from app.models.track import Track  # noqa: E402


@dataclass
class _AuditReport:
    total_examined: int = 0
    ok: list[int] = field(default_factory=list)
    missing_key: list[int] = field(default_factory=list)
    broken_key: list[tuple[int, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_examined": self.total_examined,
            "ok_count": len(self.ok),
            "missing_key_count": len(self.missing_key),
            "broken_key_count": len(self.broken_key),
            "missing_key_track_ids": self.missing_key,
            "broken_key_track_ids": [tid for tid, _ in self.broken_key],
            "broken_key_details": [
                {"track_id": tid, "manifest_key": key}
                for tid, key in self.broken_key
            ],
        }


async def _list_candidate_tracks(
    limit: int | None,
) -> list[Track]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Track)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                Track.access_mode == "internal_stream",
                Track.processing_status == "active",
            )
            .order_by(Track.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _audit(
    limit: int | None,
    concurrency: int,
) -> _AuditReport:
    tracks = await _list_candidate_tracks(limit)
    report = _AuditReport(total_examined=len(tracks))
    sem = asyncio.Semaphore(concurrency)

    async def _check(track: Track) -> None:
        if not track.hls_manifest_key:
            if track.file_key:
                # Active internal-stream track with audio source but no
                # HLS bundle -> transcoding never produced a manifest
                # (or it was wiped). Frontend will fall through to
                # progressive every time.
                report.missing_key.append(track.id)
            return
        async with sem:
            try:
                exists = await object_exists(track.hls_manifest_key)
            except Exception:
                exists = False
        if exists:
            report.ok.append(track.id)
        else:
            report.broken_key.append(
                (track.id, track.hls_manifest_key)
            )

    await asyncio.gather(*[_check(t) for t in tracks])
    report.ok.sort()
    report.missing_key.sort()
    report.broken_key.sort()
    return report


def _print_human(report: _AuditReport) -> None:
    print(f"Examined: {report.total_examined} tracks")
    print(f"  OK (manifest exists in S3):    {len(report.ok)}")
    print(
        f"  Missing hls_manifest_key:      {len(report.missing_key)}"
    )
    print(
        f"  Broken hls_manifest_key (404): {len(report.broken_key)}"
    )
    if report.missing_key:
        print()
        print("Tracks with file_key but no hls_manifest_key:")
        for tid in report.missing_key:
            print(f"  - track_id={tid}")
    if report.broken_key:
        print()
        print("Tracks with hls_manifest_key pointing to missing S3 object:")
        for tid, key in report.broken_key:
            print(f"  - track_id={tid}  key={key}")


async def _main(
    limit: int | None,
    concurrency: int,
    as_json: bool,
) -> int:
    try:
        report = await _audit(limit, concurrency)
    finally:
        await dispose_engine()
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_human(report)
    if report.broken_key:
        return 2
    if report.missing_key:
        return 1
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=(
            "Audit Track.hls_manifest_key vs actual S3 objects."
        )
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only audit the most recent N candidate tracks.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=16,
        help="Max parallel S3 head_object requests (default: 16).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report.",
    )
    args = p.parse_args()
    raise SystemExit(
        asyncio.run(
            _main(args.limit, args.concurrency, args.json)
        )
    )
