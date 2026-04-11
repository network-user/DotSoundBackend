import logging
import re
import sys
from typing import Any

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
})

_REDACT_ENABLED = False


def _mask_value(key: str, value: Any) -> Any:
    if not _REDACT_ENABLED:
        return value
    if key not in _SENSITIVE_KEYS:
        return value
    s = str(value)
    if len(s) <= 4:
        return "***"
    visible = max(2, len(s) // 5)
    return s[:visible] + "***" + s[-visible:]


def _redact_processor(
    logger: Any,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    if not _REDACT_ENABLED:
        return event_dict
    return {
        k: _mask_value(k, v) for k, v in event_dict.items()
    }


def configure_logging(
    log_level: str = "INFO",
    redact: bool = True,
) -> None:
    global _REDACT_ENABLED
    _REDACT_ENABLED = redact

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
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

    structlog.configure(
        processors=shared_processors
        + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
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

    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
