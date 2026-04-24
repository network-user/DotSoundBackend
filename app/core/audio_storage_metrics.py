import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def log_blob_dedup_hit(
    *,
    size_bytes: int,
    content_sha256: str,
) -> None:
    logger.info(
        "audio_blob_dedup_hit",
        size_bytes=size_bytes,
        content_sha256=content_sha256,
    )
    logger.info(
        "audio_blob_s3_bytes_saved_cumulative",
        size_bytes=size_bytes,
    )


def log_blob_dedup_miss(
    *,
    size_bytes: int,
    content_sha256: str,
) -> None:
    logger.info(
        "audio_blob_dedup_miss",
        size_bytes=size_bytes,
        content_sha256=content_sha256,
    )


def log_s3_put_skipped(
    *,
    content_sha256: str,
) -> None:
    logger.info(
        "audio_blob_s3_put_skipped",
        content_sha256=content_sha256,
    )
