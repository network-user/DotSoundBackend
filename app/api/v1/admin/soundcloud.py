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

import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import structlog
from dotsound_private_core.services.sc_track_policy import (
    evaluate_soundcloud_track_importability,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.dependencies import require_capability
from app.models.user import User
from app.services.outbound_proxy import (
    get_outbound_proxy,
    outbound_proxy_configured,
)
from app.services.soundcloud_service import (
    _SC_API_BASE,
    _SC_MANIFEST_BROWSER_HEADERS,
)

router = APIRouter(
    prefix="/soundcloud",
    tags=["admin-soundcloud"],
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_TRANSCODING_PROBES = 6
_MAX_PLAYLIST_PREVIEW_LINES = 20
_PROBE_TIMEOUT_SECONDS = 8.0
_EGRESS_IP_TIMEOUT_SECONDS = 4.0
_EGRESS_IP_URL = "https://api.ipify.org?format=json"
_URI_ATTR_RE = re.compile(r'URI="([^"]+)"')


def _redact_proxy_url(proxy_url: str | None) -> str | None:
    if not proxy_url:
        return None
    parsed = urlsplit(proxy_url)
    netloc = parsed.netloc
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port is not None else ""
        netloc = f"***:***@{host}{port}"
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _transport_snapshot(proxy_url: str | None) -> dict[str, Any]:
    parsed = urlsplit(proxy_url) if proxy_url else None
    return {
        "outbound_configured": outbound_proxy_configured(),
        "proxied": bool(proxy_url),
        "proxy_url": _redact_proxy_url(proxy_url),
        "proxy_scheme": parsed.scheme if parsed else None,
        "proxy_host": parsed.hostname if parsed else None,
        "proxy_port": parsed.port if parsed else None,
    }


async def _fetch_egress_ip(
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    try:
        response = await client.get(
            _EGRESS_IP_URL,
            timeout=_EGRESS_IP_TIMEOUT_SECONDS,
        )
        if response.is_success:
            data = response.json()
            ip = data.get("ip") if isinstance(data, dict) else None
            return {
                "ok": bool(ip),
                "ip": ip if isinstance(ip, str) else None,
                "provider": "api.ipify.org",
                "status_code": response.status_code,
            }
        return {
            "ok": False,
            "provider": "api.ipify.org",
            "status_code": response.status_code,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "provider": "api.ipify.org",
            "error": type(exc).__name__,
        }


async def _resolve_soundcloud_url(
    client: httpx.AsyncClient,
    *,
    url: str,
    client_id: str,
) -> dict[str, Any]:
    response = await client.get(
        f"{_SC_API_BASE}/resolve",
        params={
            "url": url,
            "client_id": client_id,
        },
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "soundcloud_resolve_not_found",
                "message": "SoundCloud URL was not found.",
                "stage": "resolve",
                "upstream_status": response.status_code,
            },
        )
    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "soundcloud_client_auth_failed",
                "message": "SoundCloud client credentials were rejected.",
                "stage": "resolve",
                "upstream_status": response.status_code,
            },
        )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


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


def _redact_url_for_diagnostic(raw: str) -> str:
    if "?" not in raw:
        return raw
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "...", "")
        )
    path, _sep, _query = raw.partition("?")
    return f"{path}?..."


def _redact_manifest_line(raw: str) -> str:
    line = raw.strip()
    if line.startswith(("http://", "https://")):
        return _redact_url_for_diagnostic(line)
    return _URI_ATTR_RE.sub(
        lambda match: f'URI="{_redact_url_for_diagnostic(match.group(1))}"',
        line,
    )


def _key_attrs(line: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if ":" not in line:
        return attrs
    _, raw_attrs = line.split(":", 1)
    for item in raw_attrs.split(","):
        key, sep, value = item.partition("=")
        if not sep:
            continue
        attrs[key.strip().upper()] = value.strip().strip('"')
    return attrs


def _playlist_summary(
    text: str,
) -> dict[str, Any]:
    raw_lines = [line for line in text.splitlines() if line.strip()]
    key_attrs = [
        _key_attrs(line)
        for line in raw_lines
        if line.strip().startswith("#EXT-X-KEY")
    ]
    key_methods = sorted(
        {
            str(attrs["METHOD"])
            for attrs in key_attrs
            if attrs.get("METHOD")
        }
    )
    keyformats = sorted(
        {
            str(attrs.get("KEYFORMAT") or "identity")
            for attrs in key_attrs
        }
    )
    return {
        "is_hls": any(
            line.strip().startswith("#EXTM3U") for line in raw_lines[:2]
        ),
        "has_master_variants": any(
            line.strip().startswith("#EXT-X-STREAM-INF")
            for line in raw_lines
        ),
        "has_ext_x_key": bool(key_attrs),
        "key_methods": key_methods,
        "keyformats": keyformats,
        "preview_lines": [
            _redact_manifest_line(line)
            for line in raw_lines[:_MAX_PLAYLIST_PREVIEW_LINES]
        ],
    }


def _first_child_playlist_url(
    text: str,
    base_url: str,
) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue
        for candidate in lines[index + 1 :]:
            if candidate.startswith("#"):
                continue
            return urljoin(base_url, candidate)
    return None


def _diagnostic_origin() -> str | None:
    if settings.mini_app_url:
        parsed = urlsplit(settings.mini_app_url)
        if parsed.scheme and parsed.netloc:
            return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    for origin in settings.allowed_origins_list:
        if origin and origin != "*":
            return origin
    return None


async def _fetch_playlist_probe(
    client: httpx.AsyncClient,
    url: str,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    headers: dict[str, str] = {
        "Accept": (
            "application/vnd.apple.mpegurl,application/x-mpegURL,"
            "text/plain,*/*"
        ),
    }
    origin = _diagnostic_origin()
    if origin:
        headers["Origin"] = origin
    try:
        response = await client.get(
            url,
            headers=headers,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        return {
            "probe": "transport_error",
            "error": type(exc).__name__,
        }
    summary: dict[str, Any] = {
        "probe": "completed",
        "status_code": response.status_code,
        "ok": response.is_success,
        "content_type": response.headers.get("content-type"),
        "cors": {
            "access_control_allow_origin": response.headers.get(
                "access-control-allow-origin"
            ),
            "access_control_allow_credentials": response.headers.get(
                "access-control-allow-credentials"
            ),
        },
    }
    if response.is_success:
        text = response.text
        summary.update(_playlist_summary(text))
        child_url = _first_child_playlist_url(text, url)
        if child_url:
            child = (
                await _fetch_playlist_probe(
                    client,
                    child_url,
                    depth=depth + 1,
                )
                if depth == 0
                else {"probe": "skipped_depth_limit"}
            )
            summary["first_child_playlist"] = {
                **child,
                "url": _redact_url_for_diagnostic(child_url),
            }
    return summary


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
    result: dict[str, Any] = {
        **base_summary,
        "probe": "completed",
        "status_code": response.status_code,
        "ok": response.is_success,
    }
    if not response.is_success:
        return result

    try:
        data = response.json()
    except ValueError:
        data = None
    stream_url = data.get("url") if isinstance(data, dict) else None
    if isinstance(stream_url, str) and stream_url:
        parsed = urlsplit(stream_url)
        result["stream_url_present"] = True
        result["stream_url_host"] = parsed.hostname
        result["stream_url_redacted"] = _redact_url_for_diagnostic(
            stream_url
        )
        protocol = str(base_summary.get("protocol") or "").lower()
        mime_type = str(base_summary.get("mime_type") or "").lower()
        if protocol.endswith("hls") or "mpegurl" in mime_type:
            result["playlist_probe"] = await _fetch_playlist_probe(
                client,
                stream_url,
            )
    else:
        result["stream_url_present"] = False
    return result


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

    proxy_url = get_outbound_proxy("soundcloud")
    transport = _transport_snapshot(proxy_url)
    async with httpx.AsyncClient(
        timeout=_PROBE_TIMEOUT_SECONDS,
        proxy=proxy_url,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        egress_ip = await _fetch_egress_ip(client)
        sc_data = await _resolve_soundcloud_url(
            client,
            url=url,
            client_id=client_id,
        )
        decision = evaluate_soundcloud_track_importability(sc_data)

        probes: list[dict[str, Any]] = []
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

        if transcodings_raw:
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
        proxied=transport["proxied"],
        egress_ip=egress_ip.get("ip"),
    )

    return {
        "request": {
            "url": url,
            "egress": {
                **transport,
                "ip_probe": egress_ip,
            },
        },
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
