from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_use_ssl: bool = False
    log_level: str = "INFO"
    complaint_threshold: int = 3
    sc_client_id: str = ""
    telegram_bot_token: str = ""
    jwt_secret: str = "changeme-set-a-strong-secret-in-production"
    jwt_expire_days: int = 7
    mini_app_url: str = ""
    telegram_bot_username: str = ""
    debug: bool = False
    redact_logs: bool = True
    allowed_origins: str = "*"
    allowed_hosts: str = "*"
    bot_internal_url: str = "http://localhost:8081"
    bot_internal_secret: str = ""

    resend_api_key: str = ""
    resend_from_email: str = "noreply@example.com"
    magic_link_ttl_minutes: int = 15
    totp_encryption_key: str = ""

    chat_encryption_key: str = ""
    ws_heartbeat_interval: int = 30
    image_chat_max_size: int = 1280
    image_avatar_max_size: int = 400
    image_cover_max_size: int = 800
    image_quality: int = 80
    image_thumbnail_size: int = 320
    image_strip_metadata: bool = True
    voice_bitrate: str = "64k"
    voice_max_duration: int = 300

    upload_malware_scan_mode: Literal["none", "lightweight", "clamav"] = "none"

    artist_enrichment_timeout_seconds: float = 25.0
    artist_image_max_bytes: int = 5 * 1024 * 1024
    artist_enrichment_min_confidence: float = 0.3

    outbound_user_agent: str = (
        "metadata-fetcher/1.0 " "(+mailto:webmaster@example.invalid)"
    )
    outbound_contact_email: str = ""

    lyrics_max_audio_mb: int = 50
    lyrics_search_cache_ttl_seconds: int = 7 * 24 * 3600
    lyrics_progress_ttl_seconds: int = 600
    lyrics_partial_ttl_seconds: int = 3600
    lyrics_stream_maxlen: int = 500
    lyrics_provider_timeout_seconds: int = 300

    # Post-import background lyrics orchestrator. Enqueue pacing
    # (random uniform between MIN and MAX seconds) keeps request
    # rate below the upstream's captcha threshold. COOLDOWN is the
    # pause applied after a proxy-level block signal, before the
    # next track is kicked off.
    yandex_music_import_lyrics_delay_min_seconds: float = 15.0
    yandex_music_import_lyrics_delay_max_seconds: float = 45.0
    yandex_music_import_lyrics_cooldown_seconds: float = 600.0

    # Stage 2 concurrency caps. SoundCloud public API is shared
    # across the whole backend; a parallel-import storm without a
    # global cap eats the SC_CLIENT_ID quota fast. The lyrics
    # per-track lock prevents two workers from running the same
    # generate_lyrics_task for the same track_id at the same time.
    soundcloud_global_concurrency: int = 4
    soundcloud_slot_acquire_timeout_seconds: float = 30.0
    youtube_concurrency: int = 4
    youtube_slot_acquire_timeout_seconds: float = 30.0
    bandcamp_concurrency: int = 4
    bandcamp_slot_acquire_timeout_seconds: float = 30.0
    lyrics_per_track_lock_ttl_seconds: int = 300

    # Stage 4 backpressure on ImportJob. New jobs above
    # ``import_max_concurrent_jobs`` enter the ``queued`` status;
    # the dispatcher loop promotes them to ``importing`` as soon
    # as a global slot frees up. ``import_per_user_max_concurrent``
    # caps how many slots one user can occupy at the same time, so
    # a single power-user cannot starve the queue.
    import_max_concurrent_jobs: int = 10
    import_per_user_max_concurrent: int = 2
    import_queue_dispatch_interval_seconds: float = 30.0

    # Stage 3 global post-import lyrics orchestrator. When the
    # feature flag is True, every external-import job pushes its
    # imported track ids into a shared Redis list and the global
    # orchestrator paces them through generate_lyrics_task using
    # the ``yandex_music_import_lyrics_*`` knobs. This way 100
    # parallel imports apply the SAME pacing budget to the lyrics
    # provider instead of multiplying it 100x. Disable to fall
    # back to per-job orchestrator (legacy).
    lyrics_global_orchestrator_enabled: bool = True
    lyrics_global_queue_key: str = "lyrics:queue:default"
    lyrics_global_block_cooldown_seconds: float = 600.0
    lyrics_global_max_consecutive_blocks: int = 5

    track_info_ttl_days: int = 30
    artist_supplemental_ttl_days: int = 30

    # Public selector forwarded into PrivateCore to pick the
    # lyrics provider. Internals of each provider remain opaque
    # inside PrivateCore; only the selector value (e.g. "yandex",
    # "generic") and an optional user-facing source label cross
    # the boundary — see docs/ai-boundary-policy.md, "Source
    # Attribution Exception".
    lyrics_provider_name: str = ""
    track_info_provider_name: str = ""

    # OAuth provider credentials for linked-account import.
    # Each provider needs its own app registration:
    #   Spotify:    developer.spotify.com
    #   SoundCloud: soundcloud.com/you/apps
    #   VK:         vk.com/editapp (audio scope requires manual approval)
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = ""

    soundcloud_oauth_client_id: str = ""
    soundcloud_oauth_client_secret: str = ""
    soundcloud_oauth_redirect_uri: str = ""

    vk_app_id: str = ""
    vk_app_secret: str = ""
    vk_redirect_uri: str = ""

    # Fernet key for encrypting stored OAuth access/refresh tokens.
    # If empty, falls back to totp_encryption_key.
    oauth_token_encryption_key: str = ""

    # TTL for OAuth state tokens stored in Redis (seconds).
    oauth_state_ttl_seconds: int = 600

    admin_jwt_secret: str = ""
    admin_csrf_secret: str = ""
    admin_telegram_alert_chat_id: str = ""
    admin_bundle_ttl_seconds: int = 3600

    prometheus_url: str = ""
    loki_url: str = ""
    # Shared log directory for ``poetry run`` dev: backend / bot / worker
    # write `backend.log`, `bot.log`, `compute-worker.log` here. Admin
    # reads when ``loki_url`` is empty.
    dotsound_dev_log_dir: str = ""
    tempo_url: str = ""
    otel_exporter_otlp_endpoint: str = ""
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1
    docker_socket_path: str = "/var/run/docker.sock"

    # Elasticsearch (suggest + full text search). Set ELASTICSEARCH_URL=""
    # in env to disable, or set ELASTICSEARCH_ENABLED=false.
    elasticsearch_url: str = "http://127.0.0.1:9200"
    elasticsearch_enabled: bool = True
    # If ES returns zero hits, run PostgreSQL text search (covers empty
    # index, stale data, and genuine no-match with one extra query).
    # Set to false in production if you want strict ES-only semantics.
    elasticsearch_fallback_to_postgres_on_zero: bool = True
    elasticsearch_index_tracks: str = "dotsound_tracks"
    elasticsearch_index_artists: str = "dotsound_artists"
    elasticsearch_backfill_on_empty: bool = False
    elasticsearch_playcount_flush_interval_seconds: float = 90.0
    elasticsearch_dev_bootstrap: bool = False
    elasticsearch_track_fuzziness: str = "AUTO"
    elasticsearch_fuzzy_max_expansions: int = 50

    # Compute-worker pull API protection. Comma-separated list of
    # CIDRs allowed to hit /api/v1/internal/*. Empty in prod is a
    # configuration error: the model validator below raises so the
    # service refuses to start. In dev the defaults below cover
    # localhost and Docker internal networks.
    internal_api_allowed_cidrs: str = ""
    yandex_speechkit_api_key: str = ""
    yandex_speechkit_folder_id: str = ""
    yandex_speechkit_enabled: bool = False
    yandex_speechkit_monthly_budget_rub: float = 500.0
    yandex_speechkit_rate_rub_per_minute: float = 16.0
    yandex_speechkit_soft_per_job_limit_rub: float = 10.0
    lyrics_allow_local_asr: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            o.strip() for o in self.allowed_origins.split(",") if o.strip()
        ]

    @property
    def allowed_hosts_list(self) -> list[str]:
        items = [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
        return items or ["*"]

    @property
    def internal_api_allowed_cidrs_list(self) -> list[str]:
        raw = (self.internal_api_allowed_cidrs or "").strip()
        if not raw:
            if self.debug:
                return [
                    "127.0.0.1/32",
                    "::1/128",
                    "10.0.0.0/8",
                    "172.16.0.0/12",
                    "192.168.0.0/16",
                ]
            return []
        return [piece.strip() for piece in raw.split(",") if piece.strip()]

    @model_validator(mode="after")
    def _validate_dev_only_flags(self) -> "AppSettings":
        if not self.debug and self.lyrics_allow_local_asr:
            raise ValueError(
                "LYRICS_ALLOW_LOCAL_ASR must be False in "
                "production (DEBUG=false). Local Whisper is "
                "an in-process dev escape hatch only — run a "
                "DotSoundComputeWorker instance instead."
            )
        if not self.debug and not self.internal_api_allowed_cidrs_list:
            raise ValueError(
                "INTERNAL_API_ALLOWED_CIDRS must list at "
                "least one CIDR in production (DEBUG=false). "
                "Pull-worker endpoints are otherwise reachable "
                "by anyone who can speak HTTP to the host."
            )
        return self


settings = AppSettings()
