"""Admin SoundCloud diagnostic endpoint.

Live introspection of why a specific SoundCloud track may fail to
stream from our backend. Intentionally heavy on raw provider fields
so an operator can decide whether a track is blocked, geo-restricted,
or behind a paywall — without copy-pasting credentials out of .env.

Public/private boundary: the decision logic lives in
``dotsound_private_core.sc_track_policy``; this router is a pure
transport adapter that fetches the provider payload and translates
errors into HTTP responses.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from dotsound_private_core.services.sc_track_policy import (
    evaluate_soundcloud_track_importability,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.dependencies import require_capability
from app.models.user import User
from app.services.soundcloud_service import (
    _SC_MANIFEST_BROWSER_HEADERS,
    SoundCloudService,
)

router = APIRouter(
    prefix="/soundcloud",
    tags=["admin-soundcloud"],
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_TRANSCODING_PROBES = 6
_PROBE_TIMEOUT_SECONDS = 8.0


def _summarize_transcoding(
    raw: dict[str, Any],
) -> dict[str, Any]:
    fmt = raw.get("format") if isinstance(raw, dict) else None
    if not isinstance(fmt, dict):
        fmt = {}
    return {
        "protocol": fmt.get("protocol"),
        "mime_type": fmt.get("mime_type"),
        "preset": raw.get("preset"),
        "quality": raw.get("quality"),
        "snipped": bool(raw.get("snipped")),
        "url_present": bool(
            isinstance(raw.get("url"), str) and raw.get("url")
        ),
    }


async def _probe_transcoding_manifest(
    client: httpx.AsyncClient,
    *,
    transcoding: dict[str, Any],
    client_id: str,
    track_authorization: str | None,
) -> dict[str, Any]:
    base_summary = _summarize_transcoding(transcoding)
    raw_url = transcoding.get("url") if isinstance(transcoding, dict) else None
    if not isinstance(raw_url, str) or not raw_url:
        return {**base_summary, "probe": "skipped_no_url"}

    params: dict[str, str] = {"client_id": client_id}
    if track_authorization:
        params["track_authorization"] = track_authorization

    try:
        response = await client.get(
            raw_url,
            params=params,
            headers=_SC_MANIFEST_BROWSER_HEADERS,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        return {
            **base_summary,
            "probe": "transport_error",
            "error": type(exc).__name__,
        }
    return {
        **base_summary,
        "probe": "completed",
        "status_code": response.status_code,
        "ok": response.is_success,
    }


@router.get("/diagnose")
async def diagnose_soundcloud_track(
    url: str = Query(..., min_length=1, max_length=1024),
    _admin: User = Depends(require_capability("tracks.manage")),
) -> dict[str, Any]:
    """Resolve an SC URL and probe each transcoding manifest.

    Read-only. Designed for cases where an imported SC track plays
    fine for end-users on soundcloud.com but our server cannot fetch
    its stream (geo block / Go+ / DMCA / removed track).
    """
    client_id = settings.sc_client_id or ""
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "sc_client_id_missing",
                "message": ("SC_CLIENT_ID is not configured on the backend."),
            },
        )

    sc_service = SoundCloudService(client_id, session=None)  # type: ignore[arg-type]
    sc_data = await sc_service.resolve_url(url)
    decision = evaluate_soundcloud_track_importability(sc_data)

    media = sc_data.get("media") if isinstance(sc_data, dict) else None
    transcodings_raw: list[dict[str, Any]] = []
    if isinstance(media, dict):
        candidates = media.get("transcodings")
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    transcodings_raw.append(item)

    track_auth_raw = (
        sc_data.get("track_authorization")
        if isinstance(sc_data, dict)
        else None
    )
    track_authorization = (
        track_auth_raw if isinstance(track_auth_raw, str) else None
    )

    probes: list[dict[str, Any]] = []
    if transcodings_raw:
        async with httpx.AsyncClient(
            timeout=_PROBE_TIMEOUT_SECONDS,
        ) as client:
            for transcoding in transcodings_raw[:_MAX_TRANSCODING_PROBES]:
                probes.append(
                    await _probe_transcoding_manifest(
                        client,
                        transcoding=transcoding,
                        client_id=client_id,
                        track_authorization=track_authorization,
                    )
                )

    track_meta: dict[str, Any] = {}
    if isinstance(sc_data, dict):
        for key in (
            "id",
            "title",
            "permalink_url",
            "kind",
            "policy",
            "monetization_model",
            "access",
            "streamable",
            "embeddable_by",
            "sharing",
            "state",
            "geo_blocked_countries",
            "available_countries",
        ):
            if key in sc_data:
                track_meta[key] = sc_data[key]
        user = sc_data.get("user")
        if isinstance(user, dict):
            track_meta["user_permalink"] = user.get("permalink")
            track_meta["user_country_code"] = user.get("country_code")

    logger.info(
        "sc_admin_diagnose",
        sc_url=url,
        reason=decision.reason,
        allowed=decision.allowed,
        probes_count=len(probes),
    )

    return {
        "request": {"url": url},
        "decision": {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "user_message": decision.user_message,
            "diagnostic": dict(decision.diagnostic),
        },
        "track": track_meta,
        "manifest_probes": probes,
        "track_authorization_present": bool(track_authorization),
    }
