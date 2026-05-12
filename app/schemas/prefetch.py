from pydantic import BaseModel, ConfigDict, Field


class PrefetchPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    enabled: bool
    algorithm_version: str
    hot_pool_size: int
    warm_segments_per_track: int
    initial_bytes_per_track: int
    max_storage_bytes: int
    in_memory_ttl_seconds: int
    persistent_ttl_seconds: int
    eviction_policy: str
    concurrent_prefetch_limit: int
    skip_third_party_audio_cache: bool
    lookahead_by_context: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Per-context lookahead. Keys are opaque strings "
            "from the policy (home, album, artist, playlist, "
            "genre_mix, daily_mix, weekly_mix, weekly_top, "
            "forgotten_treasures, user_choice, radio, queue, "
            "playback, search_results, "
            "similar_in_card, chat_shared, deep_link, "
            "continue_on_app_start, library)."
        ),
    )
    full_download_ahead: int = Field(
        default=0,
        ge=0,
        description=(
            "How many warmed tracks (per enqueue call) to escalate "
            "from warm prefix to full offline download. 0 on low "
            "bandwidth or save-data."
        ),
    )
