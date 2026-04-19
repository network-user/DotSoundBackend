from typing import Literal

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
    jwt_secret: str = (
        "changeme-set-a-strong-secret-in-production"
    )
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

    upload_malware_scan_mode: Literal[
        "none", "lightweight", "clamav"
    ] = "none"

    artist_enrichment_timeout_seconds: float = 25.0
    artist_image_max_bytes: int = 5 * 1024 * 1024
    artist_enrichment_min_confidence: float = 0.3

    outbound_user_agent: str = (
        "metadata-fetcher/1.0 "
        "(+mailto:webmaster@example.invalid)"
    )
    outbound_contact_email: str = ""

    lyrics_max_audio_mb: int = 50
    lyrics_search_cache_ttl_seconds: int = 7 * 24 * 3600
    lyrics_progress_ttl_seconds: int = 600
    lyrics_partial_ttl_seconds: int = 3600
    lyrics_stream_maxlen: int = 500

    track_info_ttl_days: int = 30
    artist_supplemental_ttl_days: int = 30

    admin_jwt_secret: str = ""
    admin_csrf_secret: str = ""
    admin_telegram_alert_chat_id: str = ""
    admin_bundle_ttl_seconds: int = 3600

    prometheus_url: str = ""
    loki_url: str = ""
    tempo_url: str = ""
    otel_exporter_otlp_endpoint: str = ""
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1
    docker_socket_path: str = "/var/run/docker.sock"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            o.strip()
            for o in self.allowed_origins.split(",")
            if o.strip()
        ]

    @property
    def allowed_hosts_list(self) -> list[str]:
        items = [
            h.strip()
            for h in self.allowed_hosts.split(",")
            if h.strip()
        ]
        return items or ["*"]


settings = AppSettings()
