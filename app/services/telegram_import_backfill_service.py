"""Backward-compatible aliases for internal UGC playback normalization."""

from __future__ import annotations

from app.services.ugc_playback_normalize_service import (
    UgcPlaybackNormalizeCandidate as TelegramImportBackfillCandidate,
    UgcPlaybackNormalizeItem as TelegramImportBackfillItem,
    UgcPlaybackNormalizeReport as TelegramImportBackfillReport,
    UgcPlaybackNormalizeService as TelegramImportBackfillService,
    repair_ugc_playback_normalize_task as repair_telegram_import_transcode_task,
)

__all__ = [
    "TelegramImportBackfillCandidate",
    "TelegramImportBackfillItem",
    "TelegramImportBackfillReport",
    "TelegramImportBackfillService",
    "repair_telegram_import_transcode_task",
]
