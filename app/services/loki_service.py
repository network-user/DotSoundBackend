"""Loki HTTP client with hardened LogQL.

Only allows whitelisted label selectors and rejects raw user input
that could be used to inject arbitrary LogQL into log queries.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import settings

ALLOWED_LABELS: frozenset[str] = frozenset(
    {
        "container",
        "service",
        "level",
        "stream",
        "request_id",
    }
)
ALLOWED_LEVELS: frozenset[str] = frozenset(
    {
        "debug",
        "info",
        "warning",
        "error",
        "critical",
    }
)
SAFE_VALUE_RE = re.compile(r"^[a-zA-Z0-9._\-:/]{1,128}$")
SAFE_FREE_TEXT_RE = re.compile(r"^[\w\s.,:;!?@#%&=+*/\\()\[\]{}\-]{0,256}$")


class LokiServiceError(Exception):
    pass


def _ensure_url() -> str:
    if not settings.loki_url:
        raise LokiServiceError("Loki is not configured")
    return settings.loki_url.rstrip("/")


def _build_selector(
    selectors: dict[str, str],
) -> str:
    if not selectors:
        raise LokiServiceError("at least one label selector required")
    parts: list[str] = []
    for label, value in selectors.items():
        if label not in ALLOWED_LABELS:
            raise LokiServiceError(f"label {label!r} is not allowed")
        if label == "level":
            if value not in ALLOWED_LEVELS:
                raise LokiServiceError(f"level {value!r} not allowed")
        elif not SAFE_VALUE_RE.match(value):
            raise LokiServiceError(
                f"value for {label} contains " "disallowed characters"
            )
        parts.append(f'{label}="{value}"')
    return "{" + ",".join(parts) + "}"


def _normalize_free_text(
    text: str | None,
) -> str | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    if not SAFE_FREE_TEXT_RE.match(text):
        raise LokiServiceError(
            "free-text filter contains " "disallowed characters"
        )
    return text


def build_query(
    *,
    selectors: dict[str, str],
    contains: str | None = None,
) -> str:
    selector = _build_selector(selectors)
    free = _normalize_free_text(contains)
    if free:
        escaped = free.replace("\\", "\\\\").replace('"', '\\"')
        return f'{selector} |= "{escaped}"'
    return selector


async def query_range(
    *,
    selectors: dict[str, str],
    contains: str | None = None,
    start_ns: int,
    end_ns: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    url = _ensure_url() + "/loki/api/v1/query_range"
    query = build_query(selectors=selectors, contains=contains)
    params = {
        "query": query,
        "start": str(start_ns),
        "end": str(end_ns),
        "limit": str(min(max(limit, 1), 1000)),
        "direction": "BACKWARD",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise LokiServiceError(
                f"Loki query failed: " f"HTTP {resp.status_code}"
            )
        body = resp.json()
    streams = body.get("data", {}).get("result", []) or []
    flattened: list[dict[str, Any]] = []
    for stream in streams:
        labels = stream.get("stream", {})
        for entry in stream.get("values", []):
            ts_ns, line = entry[0], entry[1]
            flattened.append(
                {
                    "ts_ns": int(ts_ns),
                    "labels": labels,
                    "line": line,
                }
            )
    return flattened


__all__ = [
    "ALLOWED_LABELS",
    "ALLOWED_LEVELS",
    "LokiServiceError",
    "build_query",
    "query_range",
]
