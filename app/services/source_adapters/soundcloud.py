from __future__ import annotations

import httpx
import structlog
from fastapi import HTTPException, status

from app.services.source_adapters.base import (
    MusicSourceAdapter,
    SourceTrack,
    StreamInfo,
)

logger = structlog.get_logger(__name__)

_SC_API_BASE = "https://api-v2.soundcloud.com"


class SoundCloudAdapter(MusicSourceAdapter):
    def __init__(self, client_id: str) -> None:
        self._client_id = client_id

    @property
    def source_name(self) -> str:
        return "soundcloud"

    async def search(
        self, query: str, limit: int = 20
    ) -> list[SourceTrack]:
        if not self._client_id:
            return []
        async with httpx.AsyncClient(
            timeout=10
        ) as client:
            r = await client.get(
                f"{_SC_API_BASE}/search",
                params={
                    "q": query,
                    "facet": "model",
                    "client_id": self._client_id,
                    "limit": limit,
                    "offset": 0,
                    "linked_partitioning": 1,
                },
            )
            if r.status_code == 401:
                logger.error(
                    "sc_client_id_expired"
                )
                return []
            r.raise_for_status()
            data = r.json()

        results: list[SourceTrack] = []
        for item in data.get("collection", []):
            if (
                item.get("kind") != "track"
                or not item.get("streamable")
            ):
                continue
            user = item.get("user", {})
            artist = user.get(
                "username"
            ) or user.get("full_name")
            dur_ms = item.get("duration")
            results.append(
                SourceTrack(
                    external_id=str(item.get("id")),
                    title=item.get(
                        "title", "Unknown"
                    ),
                    artist=artist,
                    duration_seconds=(
                        dur_ms // 1000 if dur_ms
                        else None
                    ),
                    artwork_url=item.get(
                        "artwork_url"
                    ),
                    source_url=item.get(
                        "permalink_url", ""
                    ),
                    source_uri=item.get("uri"),
                    genre=item.get("genre"),
                    extra=item,
                )
            )
        logger.info(
            "sc_adapter_search",
            query=query,
            count=len(results),
        )
        return results

    async def resolve_url(
        self, url: str
    ) -> SourceTrack:
        if not self._client_id:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail="SoundCloud not configured",
            )
        async with httpx.AsyncClient(
            timeout=10
        ) as client:
            r = await client.get(
                f"{_SC_API_BASE}/resolve",
                params={
                    "url": url,
                    "client_id": self._client_id,
                },
            )
            if r.status_code == 404:
                raise HTTPException(
                    status_code=(
                        status.HTTP_404_NOT_FOUND
                    ),
                    detail="SoundCloud track not found",
                )
            if r.status_code == 401:
                raise HTTPException(
                    status_code=(
                        status
                        .HTTP_503_SERVICE_UNAVAILABLE
                    ),
                    detail="SC client_id expired",
                )
            r.raise_for_status()
            data = r.json()

        user = data.get("user", {})
        artist = user.get(
            "username"
        ) or user.get("full_name")
        dur_ms = data.get("duration")
        return SourceTrack(
            external_id=str(data.get("id")),
            title=data.get("title", "Unknown"),
            artist=artist,
            duration_seconds=(
                dur_ms // 1000 if dur_ms else None
            ),
            artwork_url=data.get("artwork_url"),
            source_url=data.get(
                "permalink_url", url
            ),
            source_uri=data.get("uri"),
            genre=data.get("genre"),
            extra=data,
        )

    async def get_stream_info(
        self,
        source_url: str,
        prefer_hls: bool = False,
    ) -> StreamInfo:
        if not self._client_id:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail="SoundCloud not configured",
            )
        async with httpx.AsyncClient(
            timeout=10
        ) as client:
            r = await client.get(
                f"{_SC_API_BASE}/resolve",
                params={
                    "url": source_url,
                    "client_id": self._client_id,
                },
            )
            r.raise_for_status()
            sc_data = r.json()

        transcodings: list[dict] = (
            sc_data.get("media", {})
            .get("transcodings", [])
        )
        track_auth: str = sc_data.get(
            "track_authorization", ""
        )

        protocols = (
            ["hls", "progressive"]
            if prefer_hls
            else ["progressive", "hls"]
        )
        selected: dict | None = None
        for protocol in protocols:
            selected = next(
                (
                    t
                    for t in transcodings
                    if t.get("format", {}).get(
                        "protocol"
                    )
                    == protocol
                    and not t.get("snipped")
                ),
                None,
            )
            if selected:
                break

        if not selected:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail="No streamable format found",
            )

        params: dict = {
            "client_id": self._client_id
        }
        if track_auth:
            params["track_authorization"] = (
                track_auth
            )

        async with httpx.AsyncClient(
            timeout=10
        ) as client:
            r = await client.get(
                selected["url"], params=params
            )
            r.raise_for_status()
            return StreamInfo(
                url=r.json()["url"],
                protocol=selected.get(
                    "format", {}
                ).get("protocol", "progressive"),
            )
