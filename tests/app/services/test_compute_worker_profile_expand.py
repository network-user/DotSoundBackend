from __future__ import annotations

from app.services.compute_worker_service import (
    _expand_profiles_for_lyrics_claim,
)


def test_expand_remote_whisper_includes_gpu_full() -> None:
    assert _expand_profiles_for_lyrics_claim(
        ["remote_whisper"],
    ) == ["remote_whisper", "gpu_full"]


def test_expand_gpu_full_dedupes() -> None:
    assert _expand_profiles_for_lyrics_claim(
        ["gpu_full"],
    ) == ["gpu_full"]


def test_expand_preserves_order_dedupes() -> None:
    assert _expand_profiles_for_lyrics_claim(
        ["gpu_full", "remote_whisper"],
    ) == ["gpu_full", "remote_whisper"]
