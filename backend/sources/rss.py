from __future__ import annotations

from calendar import timegm
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import feedparser

from config import settings
from sources.models import SourceItem
from utils.http import HTTPClient
from utils.logger import get_logger

logger = get_logger(__name__)
DEFAULT_FEEDS = ["https://hnrss.org/frontpage"]


class RSSFetcher:
    source_name = "rss"

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        http_client: HTTPClient | None = None,
        stop_at_limit: bool = True,
    ):
        self.http_client = http_client or HTTPClient()
        self.stop_at_limit = stop_at_limit
        self.feed_urls = feed_urls if feed_urls is not None else settings.rss_feeds
        if not self.feed_urls:
            if feed_urls is None and not settings.rss_feeds_configured:
                self.feed_urls = DEFAULT_FEEDS
                logger.info("No RSS feeds configured; using default public RSS feed")
            else:
                logger.warning("No valid RSS feeds configured")
        self.last_metrics = _empty_metrics(len(self.feed_urls))
        logger.info("RSS feeds configured count=%s", len(self.feed_urls))

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        self.last_metrics = _empty_metrics(len(self.feed_urls))
        if limit <= 0 or not self.feed_urls:
            return []

        items: list[SourceItem] = []
        topic_map = {topic: topic.casefold() for topic in topics if topic.strip()}
        succeeded = 0
        failed = 0

        for feed_url in self.feed_urls:
            try:
                parsed = await self._parse_feed(feed_url)
                succeeded += 1
            except Exception as exc:
                failed += 1
                self.last_metrics["feed_failure_count"] = failed
                self.last_metrics["failed_feeds"].append(_redact_url(feed_url))
                logger.warning(
                    "RSS feed failed url=%s error=%s: %s",
                    _redact_url(feed_url),
                    type(exc).__name__,
                    exc,
                )
                continue

            if getattr(parsed, "bozo", False):
                logger.warning(
                    "RSS feed parsed with warnings url=%s error=%s",
                    _redact_url(feed_url),
                    getattr(parsed, "bozo_exception", "unknown"),
                )

            feed_title = _clean_text(getattr(parsed.feed, "title", "")) if getattr(parsed, "feed", None) else ""
            source_label = feed_title or _host_label(feed_url)
            self.last_metrics["feed_success_count"] = succeeded
            self.last_metrics["succeeded_feeds"].append(_redact_url(feed_url))

            for entry in parsed.entries:
                item = _entry_to_item(entry, feed_url, source_label, topics, topic_map)
                if item is None:
                    continue
                items.append(item)
                if self.stop_at_limit and len(items) >= limit:
                    self.last_metrics["raw_item_count"] = len(items)
                    logger.info(
                        "RSS fetch complete feeds_success=%s feeds_failed=%s raw_items=%s limit=%s",
                        succeeded,
                        failed,
                        len(items),
                        limit,
                    )
                    return items

        self.last_metrics["feed_success_count"] = succeeded
        self.last_metrics["feed_failure_count"] = failed
        self.last_metrics["raw_item_count"] = len(items)
        logger.info(
            "RSS fetch complete feeds_success=%s feeds_failed=%s raw_items=%s limit=%s",
            succeeded,
            failed,
            len(items),
            limit,
        )
        return items

    async def _parse_feed(self, feed_url: str):
        text = await self.http_client.get_text(feed_url)
        return feedparser.parse(text)


def _entry_to_item(entry, feed_url: str, source_label: str, topics: list[str], topic_map: dict[str, str]) -> SourceItem | None:
    title = _clean_text(getattr(entry, "title", ""))
    url = _normalize_url(getattr(entry, "link", ""), feed_url)
    if not title or not url:
        return None

    content = _clean_text(
        getattr(entry, "summary", "")
        or getattr(entry, "description", "")
        or _content_value(entry)
    )
    haystack = f"{title} {content}".casefold()
    matched_topics = [topic for topic, key in topic_map.items() if key and key in haystack]
    if topic_map and not matched_topics:
        return None

    return SourceItem(
        title=title,
        content=content,
        url=url,
        source=source_label,
        source_url=feed_url,
        published_at=_parse_feed_date(entry),
        category=matched_topics[0] if matched_topics else (topics[0] if topics else "General"),
        tags=topics,
        matched_topics=matched_topics,
        raw_score=float(len(matched_topics)),
    )


def _content_value(entry) -> str:
    values = getattr(entry, "content", None)
    if not values:
        return ""
    first = values[0]
    if isinstance(first, dict):
        return str(first.get("value", ""))
    return str(getattr(first, "value", ""))


def _parse_feed_date(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _host_label(feed_url: str) -> str:
    host = urlparse(feed_url).netloc
    return host or "RSS"


def _normalize_url(value: str, feed_url: str) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    parsed = urlparse(urljoin(feed_url, raw))
    query_pairs = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(query_pairs, doseq=True),
            "",
        )
    )


def _redact_url(feed_url: str) -> str:
    parsed = urlparse(feed_url)
    if not parsed.query:
        return feed_url
    return parsed._replace(query="...").geturl()


def _empty_metrics(feed_count: int) -> dict:
    return {
        "feed_count": feed_count,
        "feed_success_count": 0,
        "feed_failure_count": 0,
        "raw_item_count": 0,
        "succeeded_feeds": [],
        "failed_feeds": [],
    }
