from typing import Literal

from pydantic import BaseModel, Field


class ListenEventRequest(BaseModel):
    track_id: int
    duration_listened: int = Field(ge=0)
    total_duration: int | None = None
    source_context: str | None = Field(
        None, max_length=30
    )
    last_position: int | None = Field(default=None, ge=0)


class BatchListenEventRequest(BaseModel):
    events: list[ListenEventRequest]


class SearchClickRequest(BaseModel):
    query: str = Field(max_length=256)
    results_count: int = Field(default=0, ge=0)
    clicked_track_id: int | None = None


class ClientPlaybackEventRequest(BaseModel):
    event_name: Literal[
        "radio_auto_skip_exhausted",
        "hls_fatal_error",
        "playback_source_chosen",
        "track_switch_latency",
    ]
    surface: Literal["player", "radio"]
    current_track_id: int | None = Field(default=None, ge=1)
    radio_seed_track_id: int | None = Field(default=None, ge=1)
    consecutive_skips: int = Field(default=1, ge=1, le=50)
    queue_size: int = Field(default=0, ge=0, le=100)
    error_code: str | None = Field(default=None, max_length=96)
    error_reason: str | None = Field(default=None, max_length=160)
    hls_type: str | None = Field(default=None, max_length=96)
    hls_details: str | None = Field(default=None, max_length=160)
    hls_reason: str | None = Field(default=None, max_length=160)
    hls_status: int | None = Field(default=None, ge=100, le=599)
    hls_fatal: bool | None = None
    hls_message: str | None = Field(default=None, max_length=240)
    hls_url: str | None = Field(default=None, max_length=512)
    chosen_source: (
        Literal["hls", "progressive", "third_party_stream", "cached"]
        | None
    ) = None
    tt_canplay_ms: int | None = Field(default=None, ge=0, le=120_000)
    tt_first_play_ms: int | None = Field(
        default=None, ge=0, le=120_000
    )
    effective_type: str | None = Field(default=None, max_length=24)
    save_data: bool | None = None
    downlink_mbps: float | None = Field(default=None, ge=0, le=10_000)
