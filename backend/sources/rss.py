from datetime import datetime

import feedparser

from config import settings
from sources.models import SourceItem


class RSSFetcher:
    source_name = "rss"

    def __init__(self, feed_urls: list[str] | None = None):
        self.feed_urls = feed_urls if feed_urls is not None else settings.rss_feeds

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        items: list[SourceItem] = []
        topic_keys = [topic.casefold() for topic in topics]

        for feed_url in self.feed_urls:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                haystack = f"{title} {summary}".casefold()
                if topic_keys and not any(topic in haystack for topic in topic_keys):
                    continue
                items.append(
                    SourceItem(
                        title=title,
                        url=getattr(entry, "link", feed_url),
                        source=self.source_name,
                        summary=summary,
                        published_at=_parse_feed_date(entry),
                        tags=topics,
                    )
                )
                if len(items) >= limit:
                    return items
        return items


def _parse_feed_date(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6])
