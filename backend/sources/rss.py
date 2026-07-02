from __future__ import annotations

from datetime import datetime

import feedparser

from config import settings
from sources.models import SourceItem
from utils.logger import get_logger

logger = get_logger(__name__)


class RSSFetcher:
    source_name = "rss"

    def __init__(self, feed_urls: list[str] | None = None):
        self.feed_urls = feed_urls if feed_urls is not None else settings.rss_feeds
        if not self.feed_urls:
            self.feed_urls = ["https://hnrss.org/frontpage"]

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        items: list[SourceItem] = []
        topic_keys = [topic.casefold() for topic in topics]

        try:
            for feed_url in self.feed_urls:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries:
                    title = getattr(entry, "title", "")
                    content = getattr(entry, "summary", "")
                    haystack = f"{title} {content}".casefold()
                    if topic_keys and not any(topic in haystack for topic in topic_keys):
                        continue
                    items.append(
                        SourceItem(
                            title=title,
                            content=content,
                            url=getattr(entry, "link", feed_url),
                            source=self.source_name,
                            published_at=_parse_feed_date(entry),
                            category=topics[0] if topics else None,
                            tags=topics,
                        )
                    )
                    if len(items) >= limit:
                        return items
        except Exception:
            logger.exception("RSS fetch failed; using safe mock items")

        return items or mock_items(topics, limit)


def _parse_feed_date(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6])


def mock_items(topics: list[str], limit: int) -> list[SourceItem]:
    interests = topics or ["technology"]
    items: list[SourceItem] = []
    for index, topic in enumerate(interests, start=1):
        items.append(
            SourceItem(
                title=f"{topic} daily signal #{index}",
                content=(
                    f"Mock digest item about {topic}. This placeholder is used when RSS "
                    "feeds are unavailable, so the local MVP can still run end-to-end."
                ),
                url=f"https://example.com/digest/{topic.replace(' ', '-').lower()}",
                source="mock-rss",
                published_at=None,
                category=topic,
                tags=[topic],
            )
        )
        if len(items) >= limit:
            break
    return items
