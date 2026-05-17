"""Thin wrapper around the PrivateCore OutboundClient for SC calls.

The OutboundClient already implements every anti-block primitive
SoundCloud needs:

* curl_cffi-based browser TLS / JA3 fingerprint impersonation
  (Chrome 124, Safari 17, Edge 101, Chrome 123/120, Safari 15);
* quarantine on 401 / 403 / 429 / 451 with per-identity cooldown;
* per-service rate limiter, circuit breaker, exponential backoff;
* sticky-session by ``sticky_key`` so a given artist / track keeps
  the same egress + profile across retries.

This module adapts that to the legacy ``SoundCloudService`` call
sites, which still expect an ``httpx.Response``-like object so we
can keep the existing JSON-parsing code unchanged.

Layered on top:

* dead-track short-circuit (``sc_dead_track_cache``);
* refresh of the public ``client_id`` on 401 via the existing
  ``sc_client_id_manager`` (PrivateCore does not know about it);
* mapping of every classified ``ScErrorKind`` into the legacy
  ``SoundCloudRateLimitError`` / ``SoundCloudTrackUnavailable``
  exceptions that callers already understand.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import structlog
from dotsound_private_core.services.outbound import OutboundClient
from dotsound_private_core.services.outbound.errors import (
    OutboundExhaustedError,
)
from dotsound_private_core.services.sc_anti_block_policy import (
    ScAction,
    ScErrorKind,
    backoff_for_rate_limit,
    backoff_for_transient,
    classify_sc_response,
)

from app.services import sc_dead_track_cache

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ScBrowserResponse:
    """Subset of ``httpx.Response`` used by SoundCloudService.

    The legacy code reads ``status_code``, ``text``, ``headers`` and
    calls ``json()`` / ``raise_for_status()``; we mirror that
    surface exactly so we can drop the adapter into existing call
    sites without churn.
    """

    def __init__(
        self,
        *,
        status_code: int,
        text: str,
        content: bytes,
        headers: dict[str, str],
        url: str,
        identity: str,
    ) -> None:
        self.status_code = int(status_code)
        self.text = text
        self.content = content
        self.headers = headers
        self.url = url
        self.identity = identity

    def json(self) -> Any:  # noqa: ANN401 — mirrors httpx.Response.json
        import json

        return json.loads(self.text) if self.text else None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise ScBrowserHttpError(
                status_code=self.status_code,
                url=self.url,
                identity=self.identity,
            )


class ScBrowserHttpError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        identity: str = "",
    ) -> None:
        super().__init__(f"SC HTTP {status_code} from {identity or 'direct'}")
        self.status_code = status_code
        self.url = url
        self.identity = identity


@dataclass(frozen=True)
class ScCallOutcome:
    """Structured outcome the SoundCloudService translates into the
    legacy exceptions / return values. Returned by
    :func:`sc_get_with_anti_block`.
    """

    response: ScBrowserResponse | None
    error_kind: ScErrorKind
    attempts: int


_TRACK_REF_RE = re.compile(r"/tracks/([^/?#]+)")


def _extract_track_ref(url: str) -> str | None:
    m = _TRACK_REF_RE.search(url)
    return m.group(1) if m else None


def _build_sticky_key(sticky_key: str | None, url: str) -> str | None:
    if sticky_key:
        return sticky_key
    ref = _extract_track_ref(url)
    if ref:
        return f"sc:track:{ref}"
    return None


async def _refresh_client_id() -> str | None:
    """Force a fresh SoundCloud ``client_id`` scrape after a 401."""
    try:
        from app.services.sc_client_id_manager import on_auth_failure

        return await on_auth_failure()
    except Exception as exc:
        logger.warning(
            "sc_client_id_refresh_failed",
            error=str(exc)[:200],
        )
        return None


def _rewrite_client_id(
    params: dict[str, Any] | None,
    new_client_id: str | None,
) -> dict[str, Any] | None:
    if not new_client_id or not params:
        return params
    if "client_id" not in params:
        return params
    updated = dict(params)
    updated["client_id"] = new_client_id
    return updated


async def sc_get_with_anti_block(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = 20.0,
    sticky_key: str | None = None,
    max_attempts: int = 4,
) -> ScCallOutcome:
    """Single SoundCloud GET with full anti-block handling.

    Returns a :class:`ScCallOutcome`. The caller decides what to do
    when ``error_kind`` is not ``OK`` -- the SoundCloudService
    layer maps these to its existing ``SoundCloudRateLimitError`` /
    ``SoundCloudTrackUnavailable`` / fallback paths.

    The dead-track short-circuit is checked **before** issuing the
    request: if the URL targets ``/tracks/{ref}`` and we have a
    cached marker, we return a synthetic 410 without spending a
    Tor circuit slot.
    """
    track_ref = _extract_track_ref(url)
    if track_ref is not None and await sc_dead_track_cache.is_dead(track_ref):
        logger.debug(
            "sc_dead_track_short_circuit",
            track_ref=track_ref,
            url=url,
        )
        return ScCallOutcome(
            response=ScBrowserResponse(
                status_code=410,
                text="",
                content=b"",
                headers={},
                url=url,
                identity="dead_track_cache",
            ),
            error_kind=ScErrorKind.DEAD_TRACK,
            attempts=0,
        )

    sticky = _build_sticky_key(sticky_key, url)
    current_params = dict(params or {})
    attempts = 0

    async with OutboundClient.for_service(
        "soundcloud", sticky_key=sticky
    ) as client:
        while attempts < max_attempts:
            attempts += 1
            try:
                resp = await client.get(
                    url,
                    params=current_params or None,
                    headers=headers,
                    timeout_s=timeout_s,
                    sticky_key=sticky,
                )
            except OutboundExhaustedError:
                logger.warning(
                    "sc_outbound_all_identities_quarantined",
                    url=url,
                    attempts=attempts,
                )
                return ScCallOutcome(
                    response=None,
                    error_kind=ScErrorKind.CIRCUIT_BURNED,
                    attempts=attempts,
                )
            except Exception as exc:
                if attempts >= max_attempts:
                    logger.warning(
                        "sc_outbound_transport_exhausted",
                        url=url,
                        attempts=attempts,
                        error=str(exc)[:200],
                    )
                    raise
                delay = backoff_for_transient(attempts)
                logger.info(
                    "sc_outbound_transport_retry",
                    url=url,
                    attempt=attempts,
                    delay=delay,
                    error=str(exc)[:200],
                )
                await asyncio.sleep(delay)
                continue

            classification = classify_sc_response(resp.status_code, url=url)

            if classification.action is ScAction.PROCEED:
                br = _to_browser_response(resp, url=url)
                return ScCallOutcome(
                    response=br,
                    error_kind=ScErrorKind.OK,
                    attempts=attempts,
                )

            if classification.action is ScAction.MARK_DEAD_AND_SKIP:
                if track_ref is not None:
                    await sc_dead_track_cache.mark_dead(
                        track_ref,
                        reason=f"http_{resp.status_code}",
                    )
                br = _to_browser_response(resp, url=url)
                return ScCallOutcome(
                    response=br,
                    error_kind=ScErrorKind.DEAD_TRACK,
                    attempts=attempts,
                )

            if classification.action is ScAction.REFRESH_CLIENT_ID_AND_RETRY:
                new_cid = await _refresh_client_id()
                current_params = (
                    _rewrite_client_id(current_params, new_cid)
                    or current_params
                )
                if attempts >= max_attempts:
                    br = _to_browser_response(resp, url=url)
                    return ScCallOutcome(
                        response=br,
                        error_kind=ScErrorKind.AUTH_BURNED,
                        attempts=attempts,
                    )
                await asyncio.sleep(classification.backoff_seconds)
                continue

            if classification.action is ScAction.ROTATE_CIRCUIT_AND_RETRY:
                # The OutboundClient has already burned + rotated
                # the identity by virtue of the 403 falling into
                # its burn list, so the next loop iteration will
                # pick a fresh circuit. We just need to throttle.
                if attempts >= max_attempts:
                    br = _to_browser_response(resp, url=url)
                    return ScCallOutcome(
                        response=br,
                        error_kind=ScErrorKind.CIRCUIT_BURNED,
                        attempts=attempts,
                    )
                await asyncio.sleep(0.25 * attempts)
                continue

            if classification.action is ScAction.BACKOFF_AND_RETRY:
                if attempts >= max_attempts:
                    br = _to_browser_response(resp, url=url)
                    return ScCallOutcome(
                        response=br,
                        error_kind=classification.kind,
                        attempts=attempts,
                    )
                if classification.kind is ScErrorKind.RATE_LIMITED:
                    delay = backoff_for_rate_limit(attempts)
                else:
                    delay = backoff_for_transient(attempts)
                await asyncio.sleep(delay)
                continue

            br = _to_browser_response(resp, url=url)
            return ScCallOutcome(
                response=br,
                error_kind=classification.kind,
                attempts=attempts,
            )

    raise RuntimeError(
        "sc_get_with_anti_block: max_attempts exhausted without return"
    )


def _to_browser_response(
    resp: Any,  # noqa: ANN401 — duck-typed OutboundClient response
    *,
    url: str,
) -> ScBrowserResponse:
    return ScBrowserResponse(
        status_code=int(resp.status_code),
        text=str(resp.text or ""),
        content=(
            resp.content
            if isinstance(resp.content, bytes)
            else bytes(resp.content or b"")
        ),
        headers=dict(resp.headers or {}),
        url=str(getattr(resp, "url", url)),
        identity=str(getattr(resp, "identity", "")),
    )


__all__ = [
    "ScBrowserHttpError",
    "ScBrowserResponse",
    "ScCallOutcome",
    "sc_get_with_anti_block",
]
