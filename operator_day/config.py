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
    public_base_url: str = "http://localhost:8000"
    token_encryption_key: str = ""
    llm_primary_provider: str = "local"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "qwen3:8b"
    external_llm_enabled: bool = False
    freemodel_api_key: str = Field(default="", repr=False)
    freemodel_base_url: str = "https://api.freemodel.dev/v1"
    freemodel_fallback_base_url: str = "https://freemodel.dev/v1"
    freemodel_model: str = "gpt-5.4"
    llm_daily_token_budget: int = 200_000
    llm_smoke_enabled: bool = False
    embedding_provider: str = "local"
    embedding_model: str = "bge-m3"
    embedding_vector_size: int = 1024
    miniapp_public_url: str = "http://localhost:5173"
    enable_metrics: bool = True
    marketplace_write_mode: str = "dry_run"
    self_update_checks_enabled: bool = False

    def validate_runtime(self) -> None:
        if self.marketplace_write_mode not in {"dry_run", "live"}:
            raise ValueError("MARKETPLACE_WRITE_MODE must be dry_run or live")
        if self.app_env.lower() in {"prod", "production"}:
            missing: list[str] = []
            if not self.token_encryption_key:
                missing.append("TOKEN_ENCRYPTION_KEY")
            if not self.telegram_webhook_secret:
                missing.append("TELEGRAM_WEBHOOK_SECRET")
            if missing:
                raise ValueError(f"{', '.join(missing)} is required in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
