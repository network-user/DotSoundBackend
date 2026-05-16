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
    # Public-facing endpoint used ONLY when generating presigned URLs
    # that the browser will follow (e.g. media.<DOMAIN>). Leave empty to
    # reuse `minio_endpoint` for both internal ops and presigning.
    minio_public_endpoint: str = ""
    minio_public_use_ssl: bool = True
    log_level: str = "INFO"
    # Uvicorn root uses ``LOG_LEVEL``. This caps noisy third-party
    # loggers (Elasticsearch transport, urllib3, httpx, …). Use DEBUG
    # when you need to trace a client. Env: ``LOG_THIRD_PARTY_LEVEL``.
    log_third_party_level: str = "WARNING"
    complaint_threshold: int = 3
    sc_client_id: str = ""
    telegram_bot_token: str = ""
    # JWT_SECRET has no default on purpose: the boot guard in
    # main.py already refuses to start in prod with the placeholder,
    # but a missing/empty secret should fail validation immediately
    # rather than fall back to a known value.
    jwt_secret: str
    jwt_expire_days: int = 7
    mini_app_url: str = ""
    telegram_bot_username: str = ""
    debug: bool = False
    redact_logs: bool = True
    # When redact_logs is on: False keeps correlation fields (user_id,
    # file_id, client_ip, …) in events; secrets/tokens still masked.
    redact_log_identifiers: bool = True
    allowed_origins: str = "*"
    allowed_hosts: str = "*"
    # CIDRs of reverse proxies allowed to set X-Forwarded-For.
    # Empty means rate-limiter ignores XFF and uses the direct peer.
    trusted_proxy_cidrs: str = ""
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
    clamav_host: str = "clamav"
    clamav_port: int = 3310

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

    # Hard ceilings for the audio-compute /audio endpoint that
    # serves lyrics workers. ``resolve`` covers the SC API hop in
    # ``SoundCloudService.get_stream_info`` (currently up to 2x
    # httpx 10s + 30s slot acquire). ``chunk_idle`` aborts the
    # ``_stream_sc_cdn_to_worker`` proxy if SC stops sending bytes
    # — without it the proxy can hang on the request thread until
    # the outer 600s httpx timeout fires.
    lyrics_audio_resolve_timeout_seconds: float = 45.0
    lyrics_audio_chunk_idle_seconds: float = 30.0
    #: Used only for the internal ``/internal/audio-compute/audio`` proxy
    #: to ``cf-media.sndcdn.com``. The CDN often returns 403 to
    #: non-browser ``User-Agent``/missing ``Referer``.
    lyrics_sc_cdn_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    lyrics_sc_cdn_referer: str = "https://soundcloud.com/"
    lyrics_partial_ttl_seconds: int = 3600
    lyrics_stream_maxlen: int = 500
    lyrics_provider_timeout_seconds: int = 300
    lyrics_derived_genre_mood_enabled: bool = True

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

    # Аварийный переключатель воспроизведения для SoundCloud-треков:
    #   "stream"    — текущая модель (наш плеер поверх stream URL);
    #   "reference" — карточка трека показывает только ссылку на
    #                 исходную страницу SoundCloud, наш плеер их не
    #                 проигрывает.
    # Переключение нужно держать наготове: при первой претензии от
    # правообладателя или SoundCloud перевести в "reference" и
    # отдельно разбираться. См. план Фазы 7.
    sc_playback_mode: str = "stream"
    artist_station_stale_threshold_days: int = 7
    artist_catalog_full_sync_stale_threshold_days: int = 30
    artist_catalog_enqueue_lock_ttl_seconds: int = 300
    youtube_concurrency: int = 4
    youtube_slot_acquire_timeout_seconds: float = 30.0
    bandcamp_concurrency: int = 4
    bandcamp_slot_acquire_timeout_seconds: float = 30.0
    lyrics_per_track_lock_ttl_seconds: int = 300

    # YouTube — temporarily disabled; proxy support required before
    # re-enabling. Google blocks direct server-IP requests at scale
    # (bot-gate / 429). Set YOUTUBE_ENABLED=true only after a
    # residential proxy pool is wired up.
    youtube_enabled: bool = False

    # Tor exit-node pool (SoundCloud, Bandcamp — NOT YouTube; Google blocks
    # Tor exits). Off by default; set TOR_POOL_ENABLED=true in .env to start
    # a subprocess. TOR_POOL_SIZE circuits, TOR_CIRCUIT_MAX_AGE_SECONDS.
    # Requires: apt install tor / Tor Expert Bundle on Windows.
    tor_pool_enabled: bool = False
    tor_pool_size: int = 10
    tor_socks_base_port: int = 19050
    # If this falls into [``TOR_SOCKS_BASE_PORT``,
    # ``TOR_SOCKS_BASE_PORT`` + ``TOR_POOL_SIZE``) it is moved at runtime
    # (it must not double as a SOCKS listener).
    tor_control_port: int = 19060
    # Plain-text password for Tor ControlPort; leave empty to use
    # CookieAuthentication.
    tor_control_password: str = ""
    # Path to tor/tor.exe binary; leave empty to use system PATH.
    tor_bin_path: str = ""
    tor_circuit_max_age_seconds: int = 600
    tor_circuit_health_check_interval: int = 60
    tor_circuit_max_failure_rate: float = 0.3
    # One direct HTTPS request to api.ipify.org (no Tor, no env proxy) at
    # Tor pool start. Shows the public IP for the default route (with a
    # system VPN, usually the VPN address). Tor guard connections use the
    # same route unless split-tunnel excludes tor.exe.
    tor_log_outbound_public_ip: bool = False

    # Comma or newline separated httpx ``proxy=`` URLs.
    # Supported schemes: http://, https://, socks5://, socks5h://.
    # Authenticated SOCKS5: socks5://login:pass@ip:port
    # Multiple proxies are used in round-robin; each unique URL gets
    # its own pooled httpx.AsyncClient (TCP/TLS reuse).
    # Filled list wins over Tor pool; the two modes are mutually
    # exclusive (model validator rejects both being set).
    outbound_static_proxy_urls: str = ""
    outbound_static_proxy_max_urls: int = 64

    # SoundCloud transcoding-manifest fallback when outbound proxy
    # (Tor pool or ``OUTBOUND_STATIC_PROXY_URLS``) is active.
    # All SC API calls (resolve + the
    # ``/media/.../stream/{progressive,hls}`` step) use that egress.
    # Some Tor exits are silently downranked by SC at the
    # transcoding-manifest level: ``/resolve`` and our health-check
    # ``HEAD https://api.soundcloud.com`` both succeed, but every
    # transcoding ``GET`` returns ``404`` (so the user sees the
    # ``"SoundCloud stream unavailable"`` 502). When this flag is on
    # and the proxied attempt saw a 404 on every transcoding format,
    # we retry the transcoding step ONCE without a proxy. The actual
    # CDN audio fetch already runs without the API egress proxy, so
    # retrying just this step does not return us to the pre-proxy
    # exposure profile.
    sc_stream_fallback_direct_on_tor_failure: bool = False
    # Extra same-mode retries after every SoundCloud transcoding
    # manifest returns 404 through one outbound identity.
    sc_stream_manifest_proxy_retries: int = 2
    # On import, refuse to create a phantom Track row if the very
    # first playback verification fails (every SC transcoding manifest
    # returns 404, geo block, removed, Go+ only, etc.). When False, the
    # row is created and surfaced in the user library but every play
    # attempt returns 502 — that was the pre-2026-05-16 behavior. Keep
    # True in production. Tests that don't mock the SC verify path
    # should override to False or patch the verifier.
    sc_strict_import_verify: bool = True
    # When TOR_POOL_ENABLED=true, startup failure must fail closed by
    # default. Otherwise an operator can believe rotated egress is active
    # while the process silently falls back to the server IP.
    tor_pool_fail_closed: bool = True

    # Redis TTLs for cached stream URLs (seconds).
    stream_url_cache_ttl_soundcloud: int = 3600
    # SC HLS manifest URLs carry very short-lived CDN signatures.
    # Backend resolves SC HLS fresh and does not use Redis cache for it;
    # this setting is kept only for compatibility with old deployments.
    stream_url_cache_ttl_soundcloud_hls: int = 120
    stream_url_cache_ttl_bandcamp: int = 7200

    # Stage 4 backpressure on ImportJob. New jobs above
    # ``import_max_concurrent_jobs`` enter the ``queued`` status;
    # the dispatcher loop promotes them to ``importing`` as soon
    # as a global slot frees up. ``import_per_user_max_concurrent``
    # caps how many slots one user can occupy at the same time, so
    # a single power-user cannot starve the queue.
    import_max_concurrent_jobs: int = 10
    # Held at 1 because ``ImportService._get_active_job`` already
    # blocks a user from starting a second scan while any of their
    # jobs is in {scanning, ready, importing, queued}. Setting >1
    # here is unreachable from the public API and only confuses
    # the queue accounting in the dispatcher.
    import_per_user_max_concurrent: int = 1
    import_queue_dispatch_interval_seconds: float = 30.0

    # Stuck-job recovery. The dispatcher loop also acts as a sweeper:
    # any job whose status has been ``importing`` but whose row was
    # not updated for at least this many seconds is reset back to
    # ``queued`` so a fresh worker can resume it. Workers carry a
    # per-run lease token in ``tracks_data['worker_lease']`` so a
    # zombie worker that wakes up after the sweep aborts gracefully
    # without double-counting tracks.
    import_job_stuck_after_seconds: int = 600
    import_job_heartbeat_min_interval_seconds: float = 30.0

    # In-loop overhead control. Per-item ``session.refresh(job)``
    # was costing 1000 round-trips for a 1000-track import just to
    # detect cancel/lease. Cancel is now a Redis flag (no DB), and
    # the lease re-read from Postgres happens at most every N items.
    import_cancel_flag_ttl_seconds: int = 24 * 3600
    import_lease_check_every_n_items: int = 10

    # Per-track pacing for external import jobs. Prevents rapid-fire
    # API calls that trigger platform-side IP bans.
    # SLOW_MODE kicks in when a job contains more than THRESHOLD tracks.
    import_track_jitter_min_seconds: float = 0.5
    import_track_jitter_max_seconds: float = 2.0
    import_slow_mode_threshold: int = 500
    import_slow_mode_jitter_min_seconds: float = 3.0
    import_slow_mode_jitter_max_seconds: float = 8.0
    import_per_track_max_retries: int = 3
    import_per_track_retry_base_delay_seconds: float = 5.0
    import_adaptive_failure_window: int = 5
    import_adaptive_delay_multiplier_max: float = 4.0
    # SC searches for non-local-match items are prefetched in parallel
    # before the main loop runs. This concurrency value controls how
    # many search requests can be in-flight simultaneously. Keep it ≤
    # the global ``soundcloud_slot`` semaphore capacity (default 4).
    import_sc_prefetch_concurrency: int = 3
    # Prefetch chunk size: huge jobs (10k+ tracks) would otherwise
    # spawn thousands of asyncio.Task objects up front and defer
    # cancel/lease checks until the entire queue drains. Chunking
    # gives us a natural checkpoint between batches.
    import_sc_prefetch_chunk_size: int = 500

    # Telegram import path: a transient bot/network failure used to
    # kill the import for that track. With a small retry budget the
    # 502/timeout window is closed without paying for the rare
    # double-download. ``concurrency`` is intentionally tiny — the
    # Telegram bot is one process and parallel downloads against it
    # multiply the rate-limit pressure.
    import_telegram_download_max_retries: int = 2
    import_telegram_download_retry_base_delay_seconds: float = 2.0
    import_telegram_download_concurrency: int = 1

    # Audio caching: download third-party audio to S3 for local serving.
    # Off by default — enable once storage budget is confirmed.
    audio_caching_enabled: bool = False
    audio_cache_max_file_bytes: int = 100 * 1024 * 1024
    audio_cache_download_timeout_seconds: float = 120.0
    audio_cache_prefetch_max_ids: int = 20

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

    # Redis TTL for scan URL deduplication cache: (user_id, source, url)
    # → job_id. Prevents redundant provider calls when a user rescans
    # the same playlist URL within the TTL window.
    scan_url_cache_ttl_seconds: int = 3600

    # Redis TTL for SoundCloud search result cache: query → SC results.
    # Shared across all users; reduces SC API quota consumption when
    # multiple users import overlapping libraries.
    sc_search_cache_ttl_seconds: int = 3600

    # Max threads dedicated to blocking yt-dlp playlist scan calls.
    # Prevents exhausting the default ThreadPoolExecutor under load
    # (100 concurrent scans × 1 thread each = thread starvation).
    scan_executor_max_workers: int = 8

    # Hard ceiling on a single ``fetch_external_playlist`` call.
    # yt-dlp can hang for minutes on a slow upstream; without a cap
    # the scan_executor thread is held forever and eventually the
    # pool is exhausted. On timeout we surface ``provider_unavailable``
    # with code ``scan_timeout`` so the UI can prompt a retry.
    scan_timeout_seconds: float = 120.0

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
    admin_startup_alert_enabled: bool = True
    admin_startup_alert_retries: int = 8
    admin_startup_alert_retry_delay_seconds: float = 2.0
    admin_bundle_ttl_seconds: int = 3600
    admin_panel_path: str = "admin"

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
    system_resource_sampler_enabled: bool = True
    system_resource_sample_interval_seconds: int = 30
    system_resource_history_ttl_seconds: int = 7 * 24 * 3600
    system_resource_disk_path: str = "/"
    system_resource_cpu_sample_seconds: float = 0.1

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

    radio_enabled: bool = True
    radio_youtube_mix_enabled: bool = True
    radio_max_suggestions: int = 10
    playback_repair_sweep_limit: int = 30

    snippet_ffmpeg_enabled: bool = True
    snippet_external_catalog_allowed: bool = False

    #: ``uploaded_by_id`` for tracks imported during artist catalog sync.
    catalog_uploader_id: int = 1

    # Compute-worker pull API protection. Comma-separated list of
    # CIDRs allowed to hit /api/v1/internal/*. Empty in prod is a
    # configuration error: the model validator below raises so the
    # service refuses to start. In dev the defaults below cover
    # localhost and Docker internal networks.
    internal_api_allowed_cidrs: str = ""
    # Trusted reverse-proxy CIDRs for the internal worker API. When
    # empty, the internal API inherits `trusted_proxy_cidrs` so the
    # worker allowlists see the same origin IP as the public API.
    internal_api_trusted_proxies: str = ""
    #: Optional semver floor for packaged DotSoundComputeWorker binaries.
    #: When set (e.g. ``0.3.0``), ``/workers/heartbeat`` sets
    # ``worker_package_version_below_min`` from the worker's reported
    # ``X-Worker-Package-Version`` header versus this value.
    compute_worker_min_package_version: str = ""
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
    def trusted_proxy_cidrs_list(self) -> list[str]:
        return [
            c.strip()
            for c in (self.trusted_proxy_cidrs or "").split(",")
            if c.strip()
        ]

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

    @property
    def internal_api_trusted_proxies_list(self) -> list[str]:
        raw = (self.internal_api_trusted_proxies or "").strip()
        if not raw:
            return []
        return [piece.strip() for piece in raw.split(",") if piece.strip()]

    @property
    def internal_api_trusted_proxies_effective_list(self) -> list[str]:
        explicit = self.internal_api_trusted_proxies_list
        if explicit:
            return explicit
        return self.trusted_proxy_cidrs_list

    @property
    def outbound_static_proxy_urls_list(self) -> list[str]:
        raw = (self.outbound_static_proxy_urls or "").strip()
        if not raw:
            return []
        parts: list[str] = []
        for line in raw.splitlines():
            for piece in line.split(","):
                p = piece.strip()
                if p:
                    parts.append(p)
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
        cap = max(0, int(self.outbound_static_proxy_max_urls))
        return out[:cap] if cap else out

    @property
    def admin_panel_path_slug(self) -> str:
        raw = (self.admin_panel_path or "").strip().strip("/")
        if not raw:
            return "admin"
        cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
        return cleaned or "admin"

    @property
    def admin_panel_route_prefix(self) -> str:
        return f"/{self.admin_panel_path_slug}"

    @property
    def admin_api_prefix(self) -> str:
        return f"/api/v1/{self.admin_panel_path_slug}"

    @property
    def admin_api_auth_prefix(self) -> str:
        return f"{self.admin_api_prefix}/auth"

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
        if not self.debug:
            origins = self.allowed_origins_list
            if not origins or "*" in origins:
                raise ValueError(
                    "ALLOWED_ORIGINS must be a comma-separated "
                    "list of explicit origins in production "
                    "(DEBUG=false). Wildcard '*' is not accepted."
                )
            hosts = [
                h.strip() for h in self.allowed_hosts.split(",") if h.strip()
            ]
            if not hosts or "*" in hosts:
                raise ValueError(
                    "ALLOWED_HOSTS must be a comma-separated "
                    "list of explicit hostnames in production "
                    "(DEBUG=false). Wildcard '*' is not accepted."
                )
        if self.outbound_static_proxy_urls_list and self.tor_pool_enabled:
            raise ValueError(
                "OUTBOUND_STATIC_PROXY_URLS and TOR_POOL_ENABLED "
                "cannot both be set; use one egress mode."
            )
        return self


settings = AppSettings()
