from __future__ import annotations

from typing import Any

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services.artist_catalog_sync_service import ArtistCatalogSyncService


@broker.task
async def sync_artist_catalog_task(artist_id: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = ArtistCatalogSyncService(session)
        return await svc.sync_full_artist(artist_id)


@broker.task
async def sync_artist_catalog_release_task(
    artist_id: int,
    soundcloud_album_id: int,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = ArtistCatalogSyncService(session)
        return await svc.sync_single_release(artist_id, soundcloud_album_id)
