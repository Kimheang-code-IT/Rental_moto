from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HollyWing Motor API"
    debug: bool = True
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://rental:rental@localhost:5432/rental_moto"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://rental:rental@localhost:5672/rental"
    celery_result_backend: str = "redis://localhost:6379/2"
    rabbitmq_url: str = "amqp://rental:rental@localhost:5672/rental"

    jwt_secret_key: str = "dev-only-secret-change-me-in-production-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    service_token_expire_minutes: int = 10

    telegram_bot_client_id: str = "rental-telegram-bot"
    telegram_bot_client_secret: str = "dev-only-telegram-secret-change-me-0123456789abcdef"
    telegram_bot_token: str = ""
    telegram_bot_mode: str = "polling"
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = "dev-only-webhook-secret"
    telegram_reset_code_expire_minutes: int = 10
    telegram_reset_max_attempts: int = 5

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    cache_default_ttl_seconds: int = 60
    dashboard_cache_ttl_seconds: int = 60
    settings_cache_ttl_seconds: int = 120
    rate_limit_login_per_minute: int = 10
    rate_limit_refresh_per_minute: int = 30
    rate_limit_reset_per_hour: int = 5

    seed_admin_email: str = "admin@gmail.com"
    seed_admin_password: str = "123456"
    seed_admin_name: str = "System Administrator"

    task_default_max_retries: int = 5
    task_result_expire_seconds: int = 86400

    default_page_size: int = 20
    max_page_size: int = 100

    export_dir: str = "./data/exports"
    export_url_expire_seconds: int = 3600

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
