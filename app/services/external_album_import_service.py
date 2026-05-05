from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.album_service import AlbumService
from app.services.admin_artist_catalog_service import (
    AdminArtistCatalogService,
)
from app.services.admin_service import AdminService
from app.services.external_providers import scan_playlist_url
from app.schemas.admin_artist_catalog import AdminCatalogReleaseCreate


@dataclass(slots=True)
class ExternalAlbumImportResult:
    created_album_id: int | None
    created_release_id: int | None
    kind: str
    scanned_tracks: int
    matched_tracks: int


class ExternalAlbumImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._albums = AlbumService(session)
        self._catalog = AdminArtistCatalogService(session)
        self._admin = AdminService(session)

    async def import_from_url(
        self,
        *,
        user_id: int,
        source: str,
        url: str,
        target: str,
        title: str | None = None,
        artist_id: int | None = None,
    ) -> ExternalAlbumImportResult:
        payload = await scan_playlist_url(source, url)
        tracks = payload.get("tracks", [])
        kind = str(payload.get("kind", "playlist"))
        name = (title or "").strip() or "Imported album"

        if target == "album":
            album = await self._albums.create(
                user_id=user_id,
                title=name,
                description=f"Imported from {source}",
                is_public=False,
            )
            return ExternalAlbumImportResult(
                created_album_id=album.id,
                created_release_id=None,
                kind=kind,
                scanned_tracks=len(tracks),
                matched_tracks=0,
            )

        if target != "artist_catalog_release":
            msg = "unknown target"
            raise ValueError(msg)
        if artist_id is None:
            msg = "artist_id is required for artist catalog target"
            raise ValueError(msg)

        created = await self._catalog.create_release(
            artist_id,
            body=AdminCatalogReleaseCreate(
                title=name,
                release_kind=(
                    "album" if kind == "album" else "playlist"
                ),
                manual_lock=True,
            ),
        )
        if created is None:
            msg = "artist not found"
            raise ValueError(msg)

        matched_track_ids: list[int] = []
        seen: set[int] = set()
        for row in tracks:
            if not isinstance(row, dict):
                continue
            title_q = row.get("title")
            if not isinstance(title_q, str) or not title_q.strip():
                continue
            hits, _ = await self._admin.list_tracks_for_artist(
                artist_id,
                page=1,
                size=10,
                search=title_q[:128],
            )
            norm = title_q.strip().lower()
            exact = next(
                (
                    tr
                    for tr in hits
                    if (tr.title or "").strip().lower() == norm
                ),
                None,
            )
            chosen = exact or (hits[0] if hits else None)
            if chosen and chosen.id not in seen:
                matched_track_ids.append(chosen.id)
                seen.add(chosen.id)

        if matched_track_ids:
            await self._catalog.set_release_tracks(
                artist_id,
                created.id,
                matched_track_ids,
            )

        return ExternalAlbumImportResult(
            created_album_id=None,
            created_release_id=created.id,
            kind=kind,
            scanned_tracks=len(tracks),
            matched_tracks=len(matched_track_ids),
        )
