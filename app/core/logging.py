import hashlib
import logging
import sys
from typing import Any
from urllib.parse import urlparse

import structlog

_SENSITIVE_KEYS = frozenset({
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
})

_FULL_REDACT_KEYS = frozenset({
    "worker_secret",
    "x-worker-signature",
    "x_worker_signature",
    "signature",
    "signature_hex",
    "cookie",
    "set-cookie",
    "authorization",
})

_HASH_AND_LEN_KEYS = frozenset({
    "lyrics_text",
    "plain_text",
})

_COUNT_KEYS = frozenset({
    "synced_lines",
})

_REDACT_ENABLED = False


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
    return hashlib.sha256(
        value.encode("utf-8", errors="ignore")
    ).hexdigest()


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
        if lkey in _HASH_AND_LEN_KEYS and isinstance(
            value, str
        ):
            out[key + "_sha256"] = _hash_text(value)
            out[key + "_len"] = len(value)
            continue
        if lkey in _COUNT_KEYS and isinstance(value, list):
            out[key + "_count"] = len(value)
            continue
        if isinstance(value, str) and value.startswith(
            ("http://", "https://")
        ) and ("?" in value or len(value) > 200):
            out[key] = _redact_url(value)
            continue
        out[key] = _mask_value(key, value)
    return out


def configure_logging(
    log_level: str = "INFO",
    redact: bool = True,
    json_output: bool = False,
) -> None:
    global _REDACT_ENABLED
    _REDACT_ENABLED = redact

    level = getattr(
        logging, log_level.upper(), logging.INFO
    )

    shared_processors: list[
        structlog.types.Processor
    ] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(
            fmt="iso", utc=True
        ),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        _redact_processor,
    ]

    if json_output:
        renderer: structlog.types.Processor = (
            structlog.processors.JSONRenderer()
        )
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True
        )

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

    for noisy in (
        "uvicorn.access",
        "sqlalchemy.engine",
    ):
        logging.getLogger(noisy).setLevel(
            logging.WARNING
        )
