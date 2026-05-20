from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable
from urllib.parse import quote

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.album import Album
from app.models.artist import Artist, TrackArtist
from app.models.listen_event import ListenEvent
from app.models.playlist import Playlist, PlaylistTrack
from app.models.promotion import (
    PROMOTION_ENTITY_TYPES,
    PROMOTION_SURFACES,
    Promotion,
)
from app.models.track import Track
from app.repositories.promotion import PromotionRepository
from app.schemas.promotion import (
    PromotionAdminDetail,
    PromotionAdminItem,
    PromotionEntityRef,
    PromotionPublic,
    PromotionStatsResponse,
)
from app.services.promotion_policy_adapter import (
    PromotionView,
    UserContext,
    select_active,
)

UNSET: object = object()
_UNSET: object = UNSET

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_COVER_PROXY_PREFIX = "/api/v1/tracks/cover_proxy?key="


def _cover_url(key: str | None) -> str | None:
    if not key:
        return None
    return f"{_COVER_PROXY_PREFIX}{quote(key, safe='')}"


@dataclass(frozen=True)
class _EntityInfo:
    title: str
    subtitle: str | None
    cover_url: str | None
    available: bool


class PromotionValidationError(ValueError):
    pass


class PromotionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PromotionRepository(session)

    async def get_raw(self, promotion_id: int) -> Promotion | None:
        return await self._repo.get_by_id(promotion_id)

    async def list_for_admin(
        self,
        *,
        page: int = 1,
        size: int = 25,
        entity_type: str | None = None,
        is_active: bool | None = None,
        surface: str | None = None,
    ) -> tuple[list[PromotionAdminItem], int]:
        rows, total = await self._repo.list_for_admin(
            page=page,
            size=size,
            entity_type=entity_type,
            is_active=is_active,
            surface=surface,
        )
        if not rows:
            return [], total
        info_map = await self._resolve_entities(rows)
        counts = await self._repo.aggregate_event_counts_bulk(
            [r.id for r in rows]
        )
        items: list[PromotionAdminItem] = []
        for row in rows:
            info = info_map.get((row.entity_type, row.entity_id))
            availability = _availability_label(info)
            ev = counts.get(row.id, {"impression": 0, "click": 0})
            items.append(
                PromotionAdminItem(
                    id=row.id,
                    entity_type=row.entity_type,  # type: ignore[arg-type]
                    entity_id=row.entity_id,
                    entity_label=info.title if info else None,
                    surfaces=list(row.surfaces),  # type: ignore[arg-type]
                    priority=row.priority,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    is_active=row.is_active,
                    availability=availability,
                    impressions_total=ev.get("impression", 0),
                    clicks_total=ev.get("click", 0),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return items, total

    async def get_for_admin(
        self, promotion_id: int
    ) -> PromotionAdminDetail | None:
        row = await self._repo.get_by_id(promotion_id)
        if row is None:
            return None
        info_map = await self._resolve_entities([row])
        info = info_map.get((row.entity_type, row.entity_id))
        counts = await self._repo.aggregate_event_counts(row.id)
        return PromotionAdminDetail(
            id=row.id,
            entity_type=row.entity_type,  # type: ignore[arg-type]
            entity_id=row.entity_id,
            entity_label=info.title if info else None,
            surfaces=list(row.surfaces),  # type: ignore[arg-type]
            priority=row.priority,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            is_active=row.is_active,
            availability=_availability_label(info),
            impressions_total=counts.get("impression", 0),
            clicks_total=counts.get("click", 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
            title_override=row.title_override,
            subtitle_override=row.subtitle_override,
            cta_label_override=row.cta_label_override,
            cover_url_override=row.cover_url_override,
            created_by_id=row.created_by_id,
            updated_by_id=row.updated_by_id,
        )

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
        admin_user_id: int,
    ) -> Promotion:
        self._validate_inputs(entity_type, surfaces)
        await self._validate_entity_exists(entity_type, entity_id)
        row = await self._repo.create(
            entity_type=entity_type,
            entity_id=entity_id,
            surfaces=surfaces,
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
            title_override=title_override,
            subtitle_override=subtitle_override,
            cta_label_override=cta_label_override,
            cover_url_override=cover_url_override,
            created_by_id=admin_user_id,
        )
        logger.info(
            "admin_promotion_created",
            promotion_id=row.id,
            entity_type=entity_type,
            entity_id=entity_id,
            admin_id=admin_user_id,
        )
        return row

    async def update(
        self,
        promotion: Promotion,
        *,
        surfaces: list[str] | None,
        priority: int | None,
        starts_at: object = _UNSET,
        ends_at: object = _UNSET,
        is_active: bool | None,
        title_override: object = _UNSET,
        subtitle_override: object = _UNSET,
        cta_label_override: object = _UNSET,
        cover_url_override: object = _UNSET,
        admin_user_id: int,
    ) -> Promotion:
        if surfaces is not None:
            for surface in surfaces:
                if surface not in PROMOTION_SURFACES:
                    raise PromotionValidationError(
                        f"invalid surface: {surface}"
                    )
        new_starts = (
            promotion.starts_at if starts_at is _UNSET else starts_at
        )
        new_ends = promotion.ends_at if ends_at is _UNSET else ends_at
        if (
            new_starts is not None
            and new_ends is not None
            and new_ends <= new_starts  # type: ignore[operator]
        ):
            raise PromotionValidationError(
                "ends_at must be strictly after starts_at"
            )
        return await self._repo.update(
            promotion,
            surfaces=surfaces,
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
            title_override=title_override,
            subtitle_override=subtitle_override,
            cta_label_override=cta_label_override,
            cover_url_override=cover_url_override,
            updated_by_id=admin_user_id,
        )

    async def delete(self, promotion: Promotion) -> None:
        await self._repo.delete(promotion)

    async def get_for_surface(
        self,
        surface: str,
        *,
        user_id: int | None,
        locale: str | None = None,
        limit: int | None = None,
    ) -> list[PromotionPublic]:
        if surface not in PROMOTION_SURFACES:
            raise PromotionValidationError(f"invalid surface: {surface}")
        now = datetime.now(UTC)
        rows = await self._repo.list_active_for_surface(surface, now)
        if not rows:
            return []
        info_map = await self._resolve_entities(rows)
        eligible = [
            row
            for row in rows
            if self._is_publicly_available(
                info_map.get((row.entity_type, row.entity_id))
            )
        ]
        views = [
            PromotionView(
                id=r.id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                surfaces=tuple(r.surfaces),
                priority=r.priority,
                starts_at=r.starts_at,
                ends_at=r.ends_at,
            )
            for r in eligible
        ]
        ctx = UserContext(user_id=user_id, locale=locale)
        ordered = select_active(now, views, surface, ctx)
        order_index = {v.id: idx for idx, v in enumerate(ordered)}
        eligible.sort(
            key=lambda r: order_index.get(r.id, len(order_index))
        )
        if limit is not None:
            eligible = eligible[:limit]
        return [
            self._to_public(row, info_map[(row.entity_type, row.entity_id)])
            for row in eligible
        ]

    async def record_event(
        self,
        *,
        promotion_id: int,
        event_type: str,
        surface: str | None,
        user_id: int | None,
    ) -> bool:
        promotion = await self._repo.get_by_id(promotion_id)
        if promotion is None or not promotion.is_active:
            return False
        if event_type not in ("impression", "click"):
            raise PromotionValidationError(
                f"invalid event_type: {event_type}"
            )
        if surface is not None and surface not in PROMOTION_SURFACES:
            raise PromotionValidationError(f"invalid surface: {surface}")
        await self._repo.record_event(
            promotion_id=promotion_id,
            event_type=event_type,
            surface=surface,
            user_id=user_id,
        )
        return True

    async def get_stats(
        self,
        promotion_id: int,
        *,
        period_days: int = 30,
    ) -> PromotionStatsResponse | None:
        promotion = await self._repo.get_by_id(promotion_id)
        if promotion is None:
            return None
        period_days = max(1, min(period_days, 365))
        since = datetime.now(UTC) - timedelta(days=period_days)
        counts = await self._repo.aggregate_event_counts(
            promotion_id, since=since
        )
        plays = await self._count_plays(promotion, since)
        impressions = counts.get("impression", 0)
        clicks = counts.get("click", 0)
        ctr = (clicks / impressions) if impressions > 0 else 0.0
        return PromotionStatsResponse(
            promotion_id=promotion_id,
            period_days=period_days,
            impressions=impressions,
            clicks=clicks,
            plays=plays,
            ctr=round(ctr, 4),
        )

    @staticmethod
    def _validate_inputs(
        entity_type: str,
        surfaces: list[str],
    ) -> None:
        if entity_type not in PROMOTION_ENTITY_TYPES:
            raise PromotionValidationError(
                f"invalid entity_type: {entity_type}"
            )
        for surface in surfaces:
            if surface not in PROMOTION_SURFACES:
                raise PromotionValidationError(
                    f"invalid surface: {surface}"
                )
        if len(set(surfaces)) != len(surfaces):
            raise PromotionValidationError("surfaces must be unique")

    async def _validate_entity_exists(
        self,
        entity_type: str,
        entity_id: int,
    ) -> None:
        info_map = await self._resolve_entities_raw(
            [(entity_type, entity_id)]
        )
        if (entity_type, entity_id) not in info_map:
            raise PromotionValidationError(
                f"{entity_type} #{entity_id} not found"
            )

    async def _resolve_entities(
        self,
        rows: Iterable[Promotion],
    ) -> dict[tuple[str, int], _EntityInfo]:
        keys = {(r.entity_type, r.entity_id) for r in rows}
        return await self._resolve_entities_raw(keys)

    async def _resolve_entities_raw(
        self,
        keys: Iterable[tuple[str, int]],
    ) -> dict[tuple[str, int], _EntityInfo]:
        by_type: dict[str, list[int]] = {}
        for et, eid in keys:
            by_type.setdefault(et, []).append(eid)
        out: dict[tuple[str, int], _EntityInfo] = {}

        if "artist" in by_type:
            result = await self._session.execute(
                select(Artist).where(Artist.id.in_(by_type["artist"]))
            )
            for artist in result.scalars().all():
                out[("artist", artist.id)] = _EntityInfo(
                    title=artist.name,
                    subtitle=None,
                    cover_url=_cover_url(artist.image_key),
                    available=True,
                )

        if "track" in by_type:
            result = await self._session.execute(
                select(Track).where(Track.id.in_(by_type["track"]))
            )
            for track in result.scalars().all():
                out[("track", track.id)] = _EntityInfo(
                    title=track.title,
                    subtitle=track.artist,
                    cover_url=_cover_url(track.cover_key),
                    available=(
                        track.is_active
                        and track.is_public
                        and track.deleted_at is None
                    ),
                )

        if "playlist" in by_type:
            result = await self._session.execute(
                select(Playlist).where(
                    Playlist.id.in_(by_type["playlist"])
                )
            )
            for playlist in result.scalars().all():
                out[("playlist", playlist.id)] = _EntityInfo(
                    title=playlist.name,
                    subtitle=playlist.description,
                    cover_url=_cover_url(playlist.cover_key),
                    available=playlist.is_public,
                )

        if "album" in by_type:
            result = await self._session.execute(
                select(Album).where(Album.id.in_(by_type["album"]))
            )
            for album in result.scalars().all():
                out[("album", album.id)] = _EntityInfo(
                    title=album.title,
                    subtitle=album.description,
                    cover_url=_cover_url(album.cover_key),
                    available=album.is_public,
                )

        return out

    @staticmethod
    def _is_publicly_available(info: _EntityInfo | None) -> bool:
        return info is not None and info.available

    def _to_public(
        self,
        row: Promotion,
        info: _EntityInfo,
    ) -> PromotionPublic:
        title = row.title_override or info.title
        subtitle = (
            row.subtitle_override
            if row.subtitle_override is not None
            else info.subtitle
        )
        cover_url = row.cover_url_override or info.cover_url
        return PromotionPublic(
            id=row.id,
            entity_type=row.entity_type,  # type: ignore[arg-type]
            entity_id=row.entity_id,
            surfaces=list(row.surfaces),  # type: ignore[arg-type]
            priority=row.priority,
            title=title,
            subtitle=subtitle,
            cta_label=row.cta_label_override,
            cover_url=cover_url,
            entity=PromotionEntityRef(
                entity_type=row.entity_type,  # type: ignore[arg-type]
                entity_id=row.entity_id,
                title=info.title,
                subtitle=info.subtitle,
                cover_url=info.cover_url,
            ),
        )

    async def _count_plays(
        self,
        promotion: Promotion,
        since: datetime,
    ) -> int:
        et = promotion.entity_type
        eid = promotion.entity_id
        if et == "track":
            query = select(func.count(ListenEvent.id)).where(
                ListenEvent.track_id == eid,
                ListenEvent.created_at >= since,
            )
        elif et == "artist":
            track_ids = select(TrackArtist.track_id).where(
                TrackArtist.artist_id == eid
            )
            query = select(func.count(ListenEvent.id)).where(
                ListenEvent.track_id.in_(track_ids),
                ListenEvent.created_at >= since,
            )
        elif et == "playlist":
            track_ids = select(PlaylistTrack.track_id).where(
                PlaylistTrack.playlist_id == eid
            )
            query = select(func.count(ListenEvent.id)).where(
                ListenEvent.track_id.in_(track_ids),
                ListenEvent.created_at >= since,
            )
        elif et == "album":
            track_ids = select(Track.id).where(Track.album_id == eid)
            query = select(func.count(ListenEvent.id)).where(
                ListenEvent.track_id.in_(track_ids),
                ListenEvent.created_at >= since,
            )
        else:
            return 0
        result = await self._session.execute(query)
        return int(result.scalar_one() or 0)


def _availability_label(info: _EntityInfo | None) -> str:
    if info is None:
        return "missing"
    if not info.available:
        return "hidden"
    return "available"
