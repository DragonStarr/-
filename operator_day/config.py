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
    freemodel_api_key: str = Field(default="", repr=False)
    freemodel_base_url: str = "https://api.freemodel.dev/v1"
    freemodel_fallback_base_url: str = "https://freemodel.dev/v1"
    freemodel_model: str = "claude-opus-4-8"
    llm_daily_token_budget: int = 200_000
    llm_smoke_enabled: bool = False

    def validate_runtime(self) -> None:
        if self.app_env.lower() in {"prod", "production"} and not self.token_encryption_key:
            raise ValueError("TOKEN_ENCRYPTION_KEY is required in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
