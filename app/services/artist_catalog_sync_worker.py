from __future__ import annotations

from typing import Any

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services import artist_catalog_sync_progress as acsp
from app.services.artist_catalog_sync_service import ArtistCatalogSyncService


@broker.task
async def sync_artist_catalog_task(artist_id: int) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_full_artist(artist_id)
        await acsp.set_success(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            detail=result,
        )
        return result
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            message=repr(exc),
        )
        raise


@broker.task
async def sync_artist_catalog_release_task(
    artist_id: int,
    soundcloud_album_id: int,
) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_single_release(
                artist_id,
                soundcloud_album_id,
            )
        await acsp.set_success(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            detail=result,
        )
        return result
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            message=repr(exc),
        )
        raise
