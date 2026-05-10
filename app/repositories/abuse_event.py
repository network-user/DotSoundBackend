"""Repository for the ``abuse_events`` sliding window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.abuse_event import AbuseEvent
from app.repositories.base import BaseRepository


@dataclass(frozen=True)
class RecentSignalCounts:
    ip_hits: int
    same_ip_distinct_users: int
    same_signal_distinct_users: int
    register_burst_from_ip: int
    failed_login_burst: int


_LONG_WINDOW = timedelta(hours=1)
_SHORT_WINDOW = timedelta(minutes=10)


class AbuseEventRepository(BaseRepository[AbuseEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AbuseEvent)

    async def recent_signal_counts(
        self,
        *,
        ip_masked: str | None,
        signal_hash: str | None,
        now: datetime | None = None,
    ) -> RecentSignalCounts:
        moment = now if now is not None else datetime.now(UTC)
        long_since = moment - _LONG_WINDOW
        short_since = moment - _SHORT_WINDOW

        ip_hits = 0
        same_ip_users = 0
        if ip_masked:
            ip_hits = int(
                (
                    await self._session.execute(
                        select(func.count()).where(
                            AbuseEvent.ip_masked == ip_masked,
                            AbuseEvent.created_at >= long_since,
                        )
                    )
                ).scalar_one()
            )
            same_ip_users = int(
                (
                    await self._session.execute(
                        select(
                            func.count(
                                func.distinct(AbuseEvent.user_id)
                            )
                        ).where(
                            AbuseEvent.ip_masked == ip_masked,
                            AbuseEvent.user_id.is_not(None),
                            AbuseEvent.created_at >= long_since,
                        )
                    )
                ).scalar_one()
            )

        same_signal_users = 0
        if signal_hash:
            same_signal_users = int(
                (
                    await self._session.execute(
                        select(
                            func.count(
                                func.distinct(AbuseEvent.user_id)
                            )
                        ).where(
                            AbuseEvent.signal_hash == signal_hash,
                            AbuseEvent.user_id.is_not(None),
                            AbuseEvent.created_at >= long_since,
                        )
                    )
                ).scalar_one()
            )

        register_burst = 0
        failed_login_burst = 0
        if ip_masked:
            register_burst = int(
                (
                    await self._session.execute(
                        select(func.count()).where(
                            AbuseEvent.ip_masked == ip_masked,
                            AbuseEvent.kind == "register",
                            AbuseEvent.created_at >= short_since,
                        )
                    )
                ).scalar_one()
            )
            failed_login_burst = int(
                (
                    await self._session.execute(
                        select(func.count()).where(
                            AbuseEvent.ip_masked == ip_masked,
                            AbuseEvent.kind == "login",
                            AbuseEvent.score >= 3,
                            AbuseEvent.created_at >= short_since,
                        )
                    )
                ).scalar_one()
            )

        return RecentSignalCounts(
            ip_hits=ip_hits,
            same_ip_distinct_users=same_ip_users,
            same_signal_distinct_users=same_signal_users,
            register_burst_from_ip=register_burst,
            failed_login_burst=failed_login_burst,
        )

    async def prune_older_than(
        self, *, cutoff: datetime
    ) -> int:
        result = await self._session.execute(
            delete(AbuseEvent).where(
                AbuseEvent.created_at < cutoff
            )
        )
        await self._session.flush()
        return int(result.rowcount or 0)
