from __future__ import annotations

import asyncio

from sources.arxiv import ArxivFetcher
from sources.github import GitHubTrendingFetcher
from sources.models import SourceItem
from sources.news import NewsFetcher
from sources.rss import RSSFetcher


class Collector:
    def __init__(self, fetchers=None):
        self.fetchers = fetchers or [
            RSSFetcher(),
            GitHubTrendingFetcher(),
            ArxivFetcher(),
            NewsFetcher(),
        ]

    async def collect(self, interests: list[str], limit: int) -> list[SourceItem]:
        if not interests:
            return []
        per_fetcher_limit = max(1, limit)
        results = await asyncio.gather(
            *(fetcher.fetch(interests, per_fetcher_limit) for fetcher in self.fetchers),
            return_exceptions=True,
        )

        items: list[SourceItem] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            items.extend(result)
        return items
