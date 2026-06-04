from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite+aiosqlite:///./operator_day.sqlite"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_web_app_auth_ttl_seconds: int = 86_400
    public_base_url: str = "http://localhost:8000"
    token_encryption_key: str = ""
    app_session_secret: str = Field(default="", repr=False)
    app_session_ttl_seconds: int = 3_600
    allow_demo_auth: bool = True
    llm_primary_provider: str = "local"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "qwen3:8b"
    external_llm_enabled: bool = False
    freemodel_api_key: str = Field(default="", repr=False)
    freemodel_base_url: str = "https://api.freemodel.dev/v1"
    freemodel_fallback_base_url: str = "https://freemodel.dev/v1"
    freemodel_model: str = "claude-opus-4-8"
    llm_daily_token_budget: int = 200_000
    llm_smoke_enabled: bool = False
    embedding_provider: str = "local"
    embedding_model: str = "bge-m3"
    embedding_vector_size: int = 1024
    embedding_base_url: str = ""
    embedding_api_key: str = Field(default="", repr=False)
    miniapp_public_url: str = "http://localhost:5173"
    enable_metrics: bool = True
    marketplace_write_mode: str = "dry_run"
    allow_demo_fixtures: bool = False
    self_update_checks_enabled: bool = True
    morning_scheduler_enabled: bool = True
    morning_scheduler_interval_seconds: int = 3_600
    morning_scheduler_limit: int = 10

    def is_local_env(self) -> bool:
        return self.app_env.lower() in {"local", "dev", "development", "test", "testing"}

    def validate_runtime(self) -> None:
        if self.marketplace_write_mode not in {"dry_run", "live"}:
            raise ValueError("MARKETPLACE_WRITE_MODE must be dry_run or live")
        live_env = not self.is_local_env()
        issues: list[str] = []
        if live_env and self.database_url.startswith("sqlite"):
            issues.append("SQLite is allowed only in local/test environments")
        if live_env and self.allow_demo_auth:
            issues.append("ALLOW_DEMO_AUTH must be false outside local/test environments")
        if live_env:
            missing: list[str] = []
            if not self.token_encryption_key:
                missing.append("TOKEN_ENCRYPTION_KEY")
            if not self.app_session_secret:
                missing.append("APP_SESSION_SECRET")
            if not self.telegram_bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.telegram_webhook_secret:
                missing.append("TELEGRAM_WEBHOOK_SECRET")
            if missing:
                issues.append(f"{', '.join(missing)} is required in production")
        if issues:
            raise ValueError("; ".join(issues))


@lru_cache
def get_settings() -> Settings:
    return Settings()
