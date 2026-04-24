"""Read merged tail lines from local dev log files (no Loki).

When ``settings.dotsound_dev_log_dir`` is set, the admin log API
serves the same ``items`` shape as the Loki proxy, allowing the
``Logs`` tab to work without docker observability.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.loki_service import ALLOWED_LEVELS

_SERVICE_TO_FILE: dict[str, str] = {
    "dotsound-backend": "backend.log",
    "backend": "backend.log",
    "dotsound-bot": "bot.log",
    "bot": "bot.log",
    "dotsound-compute-worker": "compute-worker.log",
    "compute-worker": "compute-worker.log",
}

_FILE_TO_SERVICE_LABEL: dict[str, str] = {
    "backend.log": "dotsound-backend",
    "bot.log": "dotsound-bot",
    "compute-worker.log": "dotsound-compute-worker",
}


def dev_log_dir_resolved() -> Path | None:
    raw = (settings.dotsound_dev_log_dir or "").strip()
    if not raw:
        return None
    p = Path(os.path.expanduser(os.path.expandvars(raw))).resolve()
    if not p.is_dir():
        return None
    return p


def is_local_dev_logs_enabled() -> bool:
    return dev_log_dir_resolved() is not None


def _tail_text(path: Path, max_bytes: int = 2_000_000) -> str:
    if not path.is_file():
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    to_read = min(size, max_bytes)
    try:
        with path.open("rb") as f:
            f.seek(size - to_read)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


_ISO_START = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
)


def _parse_line_ts_ns(line: str) -> int | None:
    m = _ISO_START.search(line.lstrip()[:64])
    if not m:
        return None
    s = m.group(1)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1_000_000_000)
    except (ValueError, OSError, OverflowError):
        return None


def _infer_level(line: str) -> str:
    low = line.lower()
    for lv in (
        "critical",
        "error",
        "warning",
        "info",
        "debug",
    ):
        if f'"{lv}"' in low or f" {lv} " in f" {low} ":
            return lv
    return "info"


def _select_files(
    selectors: dict[str, str],
) -> list[tuple[Path, str, str]]:
    """Return (path, service label for JSON, filename)."""
    base = dev_log_dir_resolved()
    if base is None:
        return []
    want = (
        selectors.get("service") or selectors.get("container") or ""
    ).strip()
    base_s = str(base) + os.sep
    if want:
        want_l = want.lower()
        fn = _SERVICE_TO_FILE.get(want_l)
        if not fn:
            return []
        p = (base / fn).resolve()
        if not str(p).startswith(base_s) or not p.is_file():
            return []
        svc = _FILE_TO_SERVICE_LABEL.get(fn, "dotsound-backend")
        return [(p, svc, fn)]
    out: list[tuple[Path, str, str]] = []
    for fn in (
        "backend.log",
        "bot.log",
        "compute-worker.log",
    ):
        p = (base / fn).resolve()
        if str(p).startswith(base_s) and p.is_file():
            out.append(
                (p, _FILE_TO_SERVICE_LABEL[fn], fn)
            )
    return out


def query_dev_logs(
    *,
    selectors: dict[str, str],
    contains: str | None,
    start_ns: int,
    end_ns: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return the same list shape as :func:`loki_service.query_range`."""
    cap = min(max(limit, 1), 2000)
    level_filter = (selectors.get("level") or "").strip().lower()
    if level_filter and level_filter not in ALLOWED_LEVELS:
        level_filter = ""

    entries: list[tuple[int, dict[str, str], str]] = []
    for path, service_host, _fn in _select_files(selectors):
        text = _tail_text(path)
        for line in text.splitlines():
            line = line.rstrip()
            if not line:
                continue
            if contains and contains not in line:
                continue
            ts_ns = _parse_line_ts_ns(line)
            if ts_ns is not None and (ts_ns < start_ns or ts_ns > end_ns):
                continue
            lv = _infer_level(line)
            if level_filter and lv != level_filter:
                continue
            if ts_ns is None:
                ts_ns = end_ns
            labels = {
                "service": service_host,
                "level": lv,
            }
            entries.append((ts_ns, labels, line))

    entries.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "ts_ns": int(t),
            "labels": dict(lbl),
            "line": ln,
        }
        for t, lbl, ln in entries[:cap]
    ]


def list_labels_for_dev() -> dict[str, list[str]]:
    return {
        "labels": sorted({"container", "service", "level"}),
        "levels": sorted(ALLOWED_LEVELS),
    }
