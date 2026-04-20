"""Per-service file logging for debug mode.

When ``settings.debug`` is True, installs a ``RotatingFileHandler`` for
each known service-namespace under ``<repo>/logs/``. Files rotate at
5 MB, 3 backups, UTF-8. Console logging keeps running alongside — file
handlers are additive, not a replacement.

When ``settings.debug`` is False, the function is a no-op: logs stay
on console only.

Idempotent: safe to call from both the FastAPI process and each
Taskiq worker subprocess on startup.
"""
from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

# Namespace → filename. Multiple namespaces can share a file (e.g.
# enrichment service + worker). Handlers attach to the logger for the
# given namespace and propagate=True stays on so console still works.
_LOG_ROUTES: dict[str, str] = {
    # ── PrivateCore providers ──────────────────────────────
    "dotsound_private_core.services.yandex_search": "yandex_search.log",
    "dotsound_private_core.services.track_info_provider": (
        "track_info.log"
    ),
    "dotsound_private_core.services.artist_supplemental_provider": (
        "artist_supplemental.log"
    ),
    "dotsound_private_core.services.lyrics_provider": (
        "lyrics_provider.log"
    ),
    "dotsound_private_core.services.artist_info_provider": (
        "artist_info.log"
    ),
    # ── Backend workers / services ─────────────────────────
    "app.services.lyrics_worker": "lyrics_worker.log",
    "app.services.lyrics_service": "lyrics_worker.log",
    "app.services.track_info_worker": "track_info_worker.log",
    "app.services.track_info_service": "track_info_worker.log",
    "app.services.artist_enrichment_worker": "enrichment_worker.log",
    "app.services.artist_enrichment_service": "enrichment_worker.log",
    "app.services.artist_supplemental_worker": (
        "supplemental_worker.log"
    ),
    # ── Admin WS / other high-traffic modules ──────────────
    "app.api.v1.admin.ws": "admin_ws.log",
    # ── Third-party http noise we want isolated ────────────
    "httpx": "http_clients.log",
    "urllib3.connectionpool": "http_clients.log",
}

_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_LOCK = threading.Lock()
_INSTALLED = False


def _resolve_log_dir(override: Path | None = None) -> Path:
    if override:
        return override
    # app/core/log_setup.py → parents[2] == repo root
    return Path(__file__).resolve().parents[2] / "logs"


def _attach(logger_name: str, filepath: Path) -> None:
    logger = logging.getLogger(logger_name)
    # Deduplicate — if another call already attached a handler with the
    # same baseFilename, skip.
    for h in logger.handlers:
        if (
            isinstance(h, RotatingFileHandler)
            and Path(h.baseFilename) == filepath
        ):
            return
    handler = RotatingFileHandler(
        filepath,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(_FORMATTER)
    handler.setLevel(logging.DEBUG)
    # Ensure the logger lets DEBUG through to our handler even if its
    # level is WARNING elsewhere — handler-level filtering still applies.
    if logger.level == logging.NOTSET or logger.level > logging.DEBUG:
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)


def setup_debug_file_logs(override: Path | None = None) -> Path | None:
    """Install per-namespace file handlers when debug is on.

    Returns the log directory when handlers are installed, None when
    debug is disabled. Safe to call repeatedly.
    """
    global _INSTALLED
    if not settings.debug:
        return None

    with _LOCK:
        if _INSTALLED:
            return _resolve_log_dir(override)
        log_dir = _resolve_log_dir(override)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        for namespace, filename in _LOG_ROUTES.items():
            try:
                _attach(namespace, log_dir / filename)
            except OSError:
                # per-file failure shouldn't break the whole setup
                continue

        _INSTALLED = True

        bootstrap = logging.getLogger(__name__)
        bootstrap.info(
            "debug_file_logs_ready | dir=%s routes=%d",
            log_dir,
            len(_LOG_ROUTES),
        )
        return log_dir


# Auto-install on import so both the FastAPI process and Taskiq worker
# subprocesses pick it up without explicit wiring everywhere.
setup_debug_file_logs()
