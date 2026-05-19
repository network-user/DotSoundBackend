"""Build enriched ``TrackFeatures`` dataclasses from DB rows.

One batched query per signal type, applied to the same set of
track_ids. Used by ``RecommendationService`` and downstream
endpoints so each request issues a fixed small number of queries
regardless of candidate count.

The dataclass shape is owned by ``dotsound_private_core``; this
module just fills it. Audio-feature vectors and mood tags are
optional — they default to ``None`` / ``[]`` until Phase 5 lands
the ``track_audio_features`` table.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from dotsound_private_core.services.recommendation_engine import (
    TrackFeatures,
)
from dotsound_private_core.services.recommendation_language_policy import (
    infer_listening_language_code,
)
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import TrackArtist
from app.models.dislike import Dislike
from app.models.like import Like
from app.models.listen_event import ListenEvent
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures

WINDOW_DAYS = 7


async def build_track_features(
    session: AsyncSession,
    tracks: list[Track],
) -> list[TrackFeatures]:
    """Return enriched ``TrackFeatures`` for the given tracks.

    Aggregates listener stats from the past ``WINDOW_DAYS`` days,
    lifetime like/dislike counts, and artist mappings — each in a
    single grouped query.
    """
    if not tracks:
        return []

    track_ids = [t.id for t in tracks]
    cutoff = datetime.now(UTC) - timedelta(
        days=WINDOW_DAYS
    )

    artist_rows = (
        await session.execute(
            select(
                TrackArtist.track_id,
                TrackArtist.artist_id,
            ).where(
                TrackArtist.track_id.in_(track_ids)
            )
        )
    ).all()
    artist_map: dict[int, list[int]] = {}
    for tid, aid in artist_rows:
        artist_map.setdefault(tid, []).append(aid)

    listen_rows = (
        await session.execute(
            select(
                ListenEvent.track_id,
                func.count(
                    func.distinct(ListenEvent.user_id)
                ).label("uniq"),
                func.count(ListenEvent.id).label(
                    "total"
                ),
                func.sum(
                    case(
                        (
                            ListenEvent.completed.is_(
                                True
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("completed"),
                func.sum(
                    case(
                        (
                            ListenEvent.skipped.is_(
                                True
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("skipped"),
            )
            .where(
                ListenEvent.track_id.in_(track_ids),
                ListenEvent.created_at >= cutoff,
            )
            .group_by(ListenEvent.track_id)
        )
    ).all()
    listen_map: dict[int, dict[str, int]] = {}
    for (
        tid,
        uniq,
        total,
        completed,
        skipped,
    ) in listen_rows:
        listen_map[tid] = {
            "uniq": int(uniq or 0),
            "total": int(total or 0),
            "completed": int(completed or 0),
            "skipped": int(skipped or 0),
        }

    like_rows = (
        await session.execute(
            select(
                Like.track_id, func.count()
            )
            .where(Like.track_id.in_(track_ids))
            .group_by(Like.track_id)
        )
    ).all()
    like_map = {tid: int(c) for tid, c in like_rows}

    dislike_rows = (
        await session.execute(
            select(
                Dislike.track_id, func.count()
            )
            .where(
                Dislike.track_id.in_(track_ids)
            )
            .group_by(Dislike.track_id)
        )
    ).all()
    dislike_map = {
        tid: int(c) for tid, c in dislike_rows
    }

    taf_rows = (
        await session.execute(
            select(TrackAudioFeatures).where(
                TrackAudioFeatures.track_id.in_(track_ids)
            )
        )
    ).scalars()
    taf_by_track: dict[int, TrackAudioFeatures] = {
        r.track_id: r for r in taf_rows
    }

    out: list[TrackFeatures] = []
    for t in tracks:
        agg = listen_map.get(t.id, {})
        total = agg.get("total", 0)
        completion_rate = (
            agg["completed"] / total
            if total > 0
            else None
        )
        skip_rate = (
            agg["skipped"] / total
            if total > 0
            else None
        )
        taf = taf_by_track.get(t.id)
        mood_tags: list[str] = []
        audio_v: list[float] | None = None
        if taf is not None and taf.mood_tags is not None:
            for x in taf.mood_tags:
                if isinstance(x, str):
                    mood_tags.append(x)
        if (
            taf is not None
            and taf.feature_vector is not None
            and isinstance(
                taf.feature_vector,
                list,
            )
        ):
            out_vec: list[float] = []
            for x in taf.feature_vector:
                with contextlib.suppress(
                    TypeError,
                    ValueError,
                ):
                    out_vec.append(float(x))
            if out_vec:
                audio_v = out_vec
        created_at = t.created_at
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        out.append(
            TrackFeatures(
                track_id=t.id,
                genre=t.genre,
                artist_ids=artist_map.get(
                    t.id, []
                ),
                play_count=t.play_count,
                created_at=created_at,
                source=t.source,
                unique_listener_count=agg.get(
                    "uniq", 0
                ),
                completion_rate_7d=completion_rate,
                skip_rate_7d=skip_rate,
                like_count=like_map.get(t.id, 0),
                dislike_count=dislike_map.get(
                    t.id, 0
                ),
                mood_tags=mood_tags,
                audio_feature_vector=audio_v,
                language_code=infer_listening_language_code(
                    t.title, t.artist
                ),
            )
        )
    return out


__all__ = ["build_track_features", "WINDOW_DAYS"]
