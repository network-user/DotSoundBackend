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

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            o.strip()
            for o in self.allowed_origins.split(",")
            if o.strip()
        ]


settings = AppSettings()
