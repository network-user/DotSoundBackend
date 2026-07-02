from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_embedding import TrackEmbedding
from app.models.user_embedding import UserEmbedding
from app.repositories.track import TrackRepository

# 5000 -> 2000: пул кандидатов целиком поднимается в память на каждый
# similar/daily-mix запрос (списки float-векторов). 2000 сохраняет
# запас по recall на текущем размере каталога и режет транзиентный
# пик RAM в 2.5 раза; вернуть выше - только вместе с ростом каталога.
_DEFAULT_NEIGHBOR_POOL = 2000


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, track_id: int) -> TrackEmbedding | None:
        result = await self._session.execute(
            select(TrackEmbedding).where(TrackEmbedding.track_id == track_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        track_id: int,
        embedding: list[float],
        model_version: str,
    ) -> TrackEmbedding:
        row = await self.get(track_id)
        now = datetime.now(UTC)
        if row is None:
            row = TrackEmbedding(
                track_id=track_id,
                embedding=embedding,
                dim=len(embedding),
                model_version=model_version,
                computed_at=now,
            )
            self._session.add(row)
        else:
            row.embedding = embedding
            row.dim = len(embedding)
            row.model_version = model_version
            row.computed_at = now
        await self._session.flush()
        return row

    async def batch_get(
        self, track_ids: Iterable[int]
    ) -> dict[int, list[float]]:
        ids = list(track_ids)
        if not ids:
            return {}
        result = await self._session.execute(
            select(
                TrackEmbedding.track_id,
                TrackEmbedding.embedding,
            ).where(TrackEmbedding.track_id.in_(ids))
        )
        out: dict[int, list[float]] = {}
        for tid, vec in result.all():
            if vec is None:
                continue
            out[int(tid)] = [float(v) for v in vec]
        return out

    async def list_tracks_missing_embedding(
        self,
        *,
        limit: int = 100,
    ) -> list[int]:
        existing_subq = select(TrackEmbedding.track_id).scalar_subquery()
        result = await self._session.execute(
            select(Track.id)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                TrackRepository._playback_listing_allowed(),
                Track.id.notin_(existing_subq),
            )
            .order_by(Track.created_at.desc())
            .limit(max(1, int(limit)))
        )
        return [int(row[0]) for row in result.all()]

    async def find_neighbors(
        self,
        *,
        seed_track_id: int,
        k: int = 10,
        exclude_ids: set[int] | None = None,
        candidate_pool: int = _DEFAULT_NEIGHBOR_POOL,
    ) -> list[tuple[int, float]]:
        if k <= 0:
            return []
        seed = await self.get(seed_track_id)
        if seed is None or not seed.embedding:
            return []
        seed_vec = [float(v) for v in seed.embedding]
        if not seed_vec:
            return []
        seed_norm = math.sqrt(sum(v * v for v in seed_vec))
        if seed_norm <= 0:
            return []

        excluded: set[int] = {seed_track_id}
        if exclude_ids:
            excluded |= set(exclude_ids)

        playable = (
            select(Track.id)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                TrackRepository._playback_listing_allowed(),
            )
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(
                TrackEmbedding.track_id,
                TrackEmbedding.embedding,
                TrackEmbedding.dim,
            )
            .where(
                TrackEmbedding.track_id.in_(playable),
                TrackEmbedding.dim == seed.dim,
            )
            .limit(max(candidate_pool, k * 4))
        )

        scored: list[tuple[int, float]] = []
        for tid_raw, vec_raw, _dim in result.all():
            tid = int(tid_raw)
            if tid in excluded:
                continue
            if not vec_raw:
                continue
            vec = [float(v) for v in vec_raw]
            if len(vec) != len(seed_vec):
                continue
            dot = 0.0
            norm_b = 0.0
            for x, y in zip(seed_vec, vec, strict=True):
                dot += x * y
                norm_b += y * y
            if norm_b <= 0:
                continue
            score = dot / (seed_norm * math.sqrt(norm_b))
            scored.append((tid, score))

        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]

    async def get_user(self, user_id: int) -> UserEmbedding | None:
        result = await self._session.execute(
            select(UserEmbedding).where(UserEmbedding.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_user(
        self,
        *,
        user_id: int,
        embedding: list[float],
        model_version: str,
    ) -> UserEmbedding:
        row = await self.get_user(user_id)
        now = datetime.now(UTC)
        if row is None:
            row = UserEmbedding(
                user_id=user_id,
                embedding=embedding,
                dim=len(embedding),
                model_version=model_version,
                computed_at=now,
            )
            self._session.add(row)
        else:
            row.embedding = embedding
            row.dim = len(embedding)
            row.model_version = model_version
            row.computed_at = now
        await self._session.flush()
        return row

    async def find_track_candidates_for_user(
        self,
        *,
        user_id: int,
        k: int = 100,
        exclude_ids: set[int] | None = None,
        candidate_pool: int = _DEFAULT_NEIGHBOR_POOL,
    ) -> list[tuple[int, float]]:
        if k <= 0:
            return []
        user_row = await self.get_user(user_id)
        if user_row is None or not user_row.embedding:
            return []
        user_vec = [float(v) for v in user_row.embedding]
        if not user_vec:
            return []
        user_norm = math.sqrt(sum(v * v for v in user_vec))
        if user_norm <= 0:
            return []

        excluded: set[int] = set(exclude_ids or set())

        playable = (
            select(Track.id)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                TrackRepository._playback_listing_allowed(),
            )
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(
                TrackEmbedding.track_id,
                TrackEmbedding.embedding,
                TrackEmbedding.dim,
            )
            .where(
                TrackEmbedding.track_id.in_(playable),
                TrackEmbedding.dim == user_row.dim,
            )
            .limit(max(candidate_pool, k * 4))
        )

        scored: list[tuple[int, float]] = []
        for tid_raw, vec_raw, _dim in result.all():
            tid = int(tid_raw)
            if tid in excluded:
                continue
            if not vec_raw:
                continue
            vec = [float(v) for v in vec_raw]
            if len(vec) != len(user_vec):
                continue
            dot = 0.0
            norm_b = 0.0
            for x, y in zip(user_vec, vec, strict=True):
                dot += x * y
                norm_b += y * y
            if norm_b <= 0:
                continue
            score = dot / (user_norm * math.sqrt(norm_b))
            scored.append((tid, score))

        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]
