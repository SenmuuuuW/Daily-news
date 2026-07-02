from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    app_name: str = "Daily WeCom Digest Bot"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    database_url: str = Field(default=f"sqlite:///{BASE_DIR / 'daily_digest.db'}")
    plan_dir: Path = BASE_DIR / "plans"
    default_plan: str = "free"

    digest_hour: int = 9
    digest_minute: int = 0
    timezone: str = "Asia/Shanghai"

    wecom_incoming_token: Optional[str] = None
    wecom_push_webhook_url: Optional[str] = None
    wecom_request_timeout_seconds: float = 10.0

    rss_feeds: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DAILY_DIGEST_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
