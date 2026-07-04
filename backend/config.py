from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
RSS_FEEDS_ENV_NAME = "DAILY_DIGEST_RSS_FEEDS"
WXPUSHER_UIDS_ENV_NAME = "DAILY_DIGEST_WXPUSHER_UIDS"
WXPUSHER_TOPIC_IDS_ENV_NAME = "DAILY_DIGEST_WXPUSHER_TOPIC_IDS"
logger = logging.getLogger(__name__)


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

    wechat_push_provider: str = "wxpusher"
    enable_wechat_push: bool = False
    wxpusher_app_token: Optional[str] = None
    wxpusher_uids_raw: Optional[str] = Field(default=None, validation_alias=WXPUSHER_UIDS_ENV_NAME)
    wxpusher_topic_ids_raw: Optional[str] = Field(default=None, validation_alias=WXPUSHER_TOPIC_IDS_ENV_NAME)

    rss_feeds_raw: Optional[str] = Field(default=None, validation_alias=RSS_FEEDS_ENV_NAME)

    _rss_feeds: list[str] = PrivateAttr(default_factory=list)
    _rss_feeds_configured: bool = PrivateAttr(default=False)
    _wxpusher_uids: list[str] = PrivateAttr(default_factory=list)
    _wxpusher_topic_ids: list[int] = PrivateAttr(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BASE_DIR / ".env"),
        env_prefix="DAILY_DIGEST_",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        self._rss_feeds_configured = self.rss_feeds_raw is not None
        self._rss_feeds = parse_rss_feeds(self.rss_feeds_raw)
        self._wxpusher_uids = parse_csv_strings(self.wxpusher_uids_raw)
        self._wxpusher_topic_ids = parse_csv_ints(self.wxpusher_topic_ids_raw, WXPUSHER_TOPIC_IDS_ENV_NAME)

    @property
    def rss_feeds(self) -> list[str]:
        return list(self._rss_feeds)

    @property
    def rss_feeds_configured(self) -> bool:
        return self._rss_feeds_configured

    @property
    def wxpusher_uids(self) -> list[str]:
        return list(self._wxpusher_uids)

    @property
    def wxpusher_topic_ids(self) -> list[int]:
        return list(self._wxpusher_topic_ids)


def parse_rss_feeds(value: str | None) -> list[str]:
    if value is None:
        return []

    raw_value = value.strip()
    if not raw_value:
        return []

    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse %s as a JSON array: %s", RSS_FEEDS_ENV_NAME, exc)
            return []

        if not isinstance(parsed, list):
            logger.warning("%s must be a JSON array or comma-separated URL list", RSS_FEEDS_ENV_NAME)
            return []

        feeds = [_normalize_feed_url(item) for item in parsed if isinstance(item, str)]
        if len(feeds) != len(parsed):
            logger.warning("Ignored non-string values in %s", RSS_FEEDS_ENV_NAME)
        return [feed for feed in feeds if feed]

    if raw_value.startswith("{"):
        logger.warning("%s must be a JSON array, not an object", RSS_FEEDS_ENV_NAME)
        return []

    return [feed for feed in (_normalize_feed_url(part) for part in raw_value.split(",")) if feed]


def _normalize_feed_url(value: str) -> str:
    return " ".join(value.strip().split())


def parse_csv_strings(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_csv_ints(value: str | None, field_name: str) -> list[int]:
    values: list[int] = []
    for part in parse_csv_strings(value):
        try:
            values.append(int(part))
        except ValueError:
            logger.warning("Ignored invalid integer value in %s", field_name)
    return values


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
