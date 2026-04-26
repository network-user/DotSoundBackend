import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

_SENSITIVE_KEYS = frozenset(
    {
        "telegram_id",
        "user_id",
        "owner_id",
        "uploader_id",
        "follower_id",
        "following_id",
        "reported_by_user_id",
        "file_id",
        "file_key",
        "token",
        "access_token",
        "jwt_secret",
        "client_ip",
        "to",
        "email",
        "code",
        "init_data",
        "magic_link_url",
        "session_token",
        "backup_code",
        "secret",
        "totp_secret",
        "worker_secret",
        "x-worker-signature",
        "x_worker_signature",
        "signature",
        "signature_hex",
        "cookie",
        "set-cookie",
        "authorization",
    }
)

_FULL_REDACT_KEYS = frozenset(
    {
        "worker_secret",
        "x-worker-signature",
        "x_worker_signature",
        "signature",
        "signature_hex",
        "cookie",
        "set-cookie",
        "authorization",
    }
)

_HASH_AND_LEN_KEYS = frozenset(
    {
        "lyrics_text",
        "plain_text",
    }
)

_COUNT_KEYS = frozenset(
    {
        "synced_lines",
    }
)

_REDACT_ENABLED = False

THIRD_PARTY_LOGGER_NAMES: tuple[str, ...] = (
    "uvicorn.access",
    "sqlalchemy.engine",
    "elastic_transport",
    "elastic_transport.node",
    "elastic_transport.node_pool",
    "elastic_transport.transport",
    "elasticsearch",
    "opensearch",
    "urllib3",
    "urllib3.connectionpool",
    "httpx",
    "httpcore",
    "httpcore.http11",
    "httpcore.connection",
    "h11",
)


def _parse_log_level_name(name: str) -> int:
    key = (name or "WARNING").upper().strip()
    parsed = getattr(logging, key, None)
    if isinstance(parsed, int):
        return parsed
    return logging.WARNING


def apply_third_party_log_levels(third_party_level: str) -> None:
    """Set levels for noisy stdlib loggers. Idempotent; safe in workers."""
    n = _parse_log_level_name(third_party_level)
    for lname in THIRD_PARTY_LOGGER_NAMES:
        logging.getLogger(lname).setLevel(n)


def _mask_value(key: str, value: Any) -> Any:
    if not _REDACT_ENABLED:
        return value
    if key not in _SENSITIVE_KEYS:
        return value
    if key.lower() in _FULL_REDACT_KEYS:
        return "***REDACTED***"
    s = str(value)
    if len(s) <= 4:
        return "***"
    visible = max(2, len(s) // 5)
    return s[:visible] + "***" + s[-visible:]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _redact_url(value: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError:
        return "***URL***"
    if not parsed.scheme:
        return value
    if not parsed.query and len(value) <= 200:
        return value
    return f"{parsed.scheme}://{parsed.netloc}/<redacted>"


def _redact_processor(
    logger: Any,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    if not _REDACT_ENABLED:
        return event_dict
    out: dict[str, Any] = {}
    for key, value in event_dict.items():
        lkey = key.lower()
        if lkey in _HASH_AND_LEN_KEYS and isinstance(value, str):
            out[key + "_sha256"] = _hash_text(value)
            out[key + "_len"] = len(value)
            continue
        if lkey in _COUNT_KEYS and isinstance(value, list):
            out[key + "_count"] = len(value)
            continue
        if (
            isinstance(value, str)
            and value.startswith(("http://", "https://"))
            and ("?" in value or len(value) > 200)
        ):
            out[key] = _redact_url(value)
            continue
        out[key] = _mask_value(key, value)
    return out


def _attach_dev_file_handler(level: int) -> None:
    """When ``DOTSOUND_DEV_LOG_DIR`` / settings ``dotsound_dev_log_dir``
    is set, duplicate structlog/stdout output to ``backend.log``.
    """
    from app.config import settings

    raw = (settings.dotsound_dev_log_dir or "").strip() or (
        os.environ.get("DOTSOUND_DEV_LOG_DIR") or ""
    ).strip()
    if not raw:
        return
    try:
        log_dir = Path(os.path.expanduser(os.path.expandvars(raw))).resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "backend.log"
        base_s = str(path)
        root = logging.getLogger()
        for h in root.handlers:
            bfn = getattr(h, "baseFilename", None)
            if bfn and str(bfn) == base_s:
                return
        fh = logging.FileHandler(
            path,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(fh)
    except OSError:
        return


def configure_logging(
    log_level: str = "INFO",
    redact: bool = True,
    json_output: bool = False,
    third_party_level: str = "WARNING",
) -> None:
    global _REDACT_ENABLED
    _REDACT_ENABLED = redact

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        _redact_processor,
    ]

    if json_output:
        renderer: structlog.types.Processor = (
            structlog.processors.JSONRenderer()
        )
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(message)s",
    )

    # Mirror console to a shared file for local admin log tail (see
    # ``DOTSOUND_DEV_LOG_DIR`` in docs / ``dotsound_dev_log_dir`` in config).
    _attach_dev_file_handler(level)
    apply_third_party_log_levels(third_party_level)
