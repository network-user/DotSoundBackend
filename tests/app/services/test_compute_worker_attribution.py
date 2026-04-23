from app.services.compute_worker_service import (
    attribution_for_remote_worker_result,
)


def test_attribution_text_only() -> None:
    s, sync = attribution_for_remote_worker_result(
        current_tier="remote_whisper",
        synced_lines=None,
        sync_profile="gpu_full",
    )
    assert s == "faster-whisper"
    assert sync is None


def test_attribution_with_sync_gpu() -> None:
    s, sync = attribution_for_remote_worker_result(
        current_tier="remote_whisper",
        synced_lines=[{"time_ms": 0, "text": "a", "confidence": 0.5}],
        sync_profile="gpu_full",
    )
    assert s == "faster-whisper"
    assert sync == "faster-whisper (GPU)"


def test_attribution_with_sync_cpu() -> None:
    s, sync = attribution_for_remote_worker_result(
        current_tier="remote_whisper",
        synced_lines=[{"time_ms": 0, "text": "a", "confidence": 0.5}],
        sync_profile="cpu_light",
    )
    assert s == "faster-whisper"
    assert sync == "faster-whisper (CPU)"


def test_attribution_nonstandard_tier() -> None:
    s, _ = attribution_for_remote_worker_result(
        current_tier="custom_tier",
        synced_lines=None,
        sync_profile=None,
    )
    assert s == "ASR (custom_tier)"
