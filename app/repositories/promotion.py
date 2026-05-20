from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy import and_ as sa_and
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion import Promotion, PromotionEvent

_UNSET: object = object()

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PromotionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, promotion_id: int) -> Promotion | None:
        return await self._session.get(Promotion, promotion_id)

    async def list_for_admin(
        self,
        *,
        page: int = 1,
        size: int = 25,
        entity_type: str | None = None,
        is_active: bool | None = None,
        surface: str | None = None,
    ) -> tuple[list[Promotion], int]:
        query = select(Promotion)
        count_query = select(func.count(Promotion.id))
        if entity_type is not None:
            query = query.where(Promotion.entity_type == entity_type)
            count_query = count_query.where(
                Promotion.entity_type == entity_type
            )
        if is_active is not None:
            query = query.where(Promotion.is_active == is_active)
            count_query = count_query.where(Promotion.is_active == is_active)

        offset = max(0, (page - 1) * size)
        query = (
            query.order_by(
                desc(Promotion.priority),
                desc(Promotion.created_at),
            )
            .offset(offset)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total = int(
            (await self._session.execute(count_query)).scalar_one()
        )
        if surface is not None:
            rows = [r for r in rows if surface in (r.surfaces or [])]
        return rows, total

    async def list_active_for_surface(
        self,
        surface: str,
        now: datetime,
    ) -> list[Promotion]:
        window_ok = sa_and(
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        )
        query = (
            select(Promotion)
            .where(
                Promotion.is_active.is_(True),
                window_ok,
            )
            .order_by(
                desc(Promotion.priority),
                desc(Promotion.created_at),
            )
        )
        result = await self._session.execute(query)
        return [
            r
            for r in result.scalars().all()
            if surface in (r.surfaces or [])
        ]

    async def list_active_by_entity_type(
        self,
        entity_type: str,
        surface: str,
        now: datetime,
    ) -> list[Promotion]:
        window_ok = sa_and(
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        )
        query = (
            select(Promotion)
            .where(
                Promotion.is_active.is_(True),
                Promotion.entity_type == entity_type,
                window_ok,
            )
            .order_by(
                desc(Promotion.priority),
                desc(Promotion.created_at),
            )
        )
        result = await self._session.execute(query)
        return [
            r
            for r in result.scalars().all()
            if surface in (r.surfaces or [])
        ]

    async def create(
        self,
        *,
        entity_type: str,
        entity_id: int,
        surfaces: list[str],
        priority: int,
        starts_at: datetime | None,
        ends_at: datetime | None,
        is_active: bool,
        title_override: str | None,
        subtitle_override: str | None,
        cta_label_override: str | None,
        cover_url_override: str | None,
        created_by_id: int | None,
    ) -> Promotion:
        row = Promotion(
            entity_type=entity_type,
            entity_id=entity_id,
            surfaces=list(surfaces),
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
            title_override=title_override,
            subtitle_override=subtitle_override,
            cta_label_override=cta_label_override,
            cover_url_override=cover_url_override,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        logger.debug(
            "db_promotion_created",
            promotion_id=row.id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        return row

    async def update(
        self,
        promotion: Promotion,
        *,
        surfaces: list[str] | None = None,
        priority: int | None = None,
        starts_at: object = _UNSET,
        ends_at: object = _UNSET,
        is_active: bool | None = None,
        title_override: object = _UNSET,
        subtitle_override: object = _UNSET,
        cta_label_override: object = _UNSET,
        cover_url_override: object = _UNSET,
        updated_by_id: int | None = None,
    ) -> Promotion:
        if surfaces is not None:
            promotion.surfaces = list(surfaces)
        if priority is not None:
            promotion.priority = priority
        if starts_at is not _UNSET:
            promotion.starts_at = starts_at  # type: ignore[assignment]
        if ends_at is not _UNSET:
            promotion.ends_at = ends_at  # type: ignore[assignment]
        if is_active is not None:
            promotion.is_active = is_active
        if title_override is not _UNSET:
            promotion.title_override = title_override  # type: ignore[assignment]
        if subtitle_override is not _UNSET:
            promotion.subtitle_override = subtitle_override  # type: ignore[assignment]
        if cta_label_override is not _UNSET:
            promotion.cta_label_override = cta_label_override  # type: ignore[assignment]
        if cover_url_override is not _UNSET:
            promotion.cover_url_override = cover_url_override  # type: ignore[assignment]
        if updated_by_id is not None:
            promotion.updated_by_id = updated_by_id
        await self._session.flush()
        await self._session.refresh(promotion)
        return promotion

    async def delete(self, promotion: Promotion) -> None:
        await self._session.delete(promotion)
        await self._session.flush()

    async def record_event(
        self,
        *,
        promotion_id: int,
        event_type: str,
        surface: str | None,
        user_id: int | None,
        occurred_at: datetime | None = None,
    ) -> PromotionEvent:
        event = PromotionEvent(
            promotion_id=promotion_id,
            event_type=event_type,
            surface=surface,
            user_id=user_id,
            occurred_at=occurred_at or datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def aggregate_event_counts(
        self,
        promotion_id: int,
        *,
        since: datetime | None = None,
    ) -> dict[str, int]:
        query = select(
            PromotionEvent.event_type,
            func.count(PromotionEvent.id),
        ).where(PromotionEvent.promotion_id == promotion_id)
        if since is not None:
            query = query.where(PromotionEvent.occurred_at >= since)
        query = query.group_by(PromotionEvent.event_type)
        result = await self._session.execute(query)
        counts: dict[str, int] = {"impression": 0, "click": 0}
        for event_type, count in result.all():
            counts[str(event_type)] = int(count)
        return counts

    async def aggregate_event_counts_bulk(
        self,
        promotion_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        if not promotion_ids:
            return {}
        query = (
            select(
                PromotionEvent.promotion_id,
                PromotionEvent.event_type,
                func.count(PromotionEvent.id),
            )
            .where(PromotionEvent.promotion_id.in_(promotion_ids))
            .group_by(
                PromotionEvent.promotion_id,
                PromotionEvent.event_type,
            )
        )
        result = await self._session.execute(query)
        out: dict[int, dict[str, int]] = {
            pid: {"impression": 0, "click": 0} for pid in promotion_ids
        }
        for promotion_id, event_type, count in result.all():
            out[int(promotion_id)][str(event_type)] = int(count)
        return out

    async def delete_events_for_promotion(self, promotion_id: int) -> int:
        result = await self._session.execute(
            delete(PromotionEvent).where(
                PromotionEvent.promotion_id == promotion_id
            )
        )
        return int(result.rowcount or 0)

    async def list_meta(
        self,
        promotion_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        if not promotion_ids:
            return {}
        query = select(Promotion).where(Promotion.id.in_(promotion_ids))
        result = await self._session.execute(query)
        out: dict[int, dict[str, Any]] = {}
        for row in result.scalars().all():
            out[int(row.id)] = {
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
            }
        return out
