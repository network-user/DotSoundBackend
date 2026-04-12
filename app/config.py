from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
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
    bot_internal_url: str = "http://localhost:8081"
    bot_internal_secret: str = ""

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

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            o.strip()
            for o in self.allowed_origins.split(",")
            if o.strip()
        ]


settings = AppSettings()
