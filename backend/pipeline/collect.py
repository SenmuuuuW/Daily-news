from __future__ import annotations

import asyncio

from sources.models import SourceItem
from sources.rss import RSSFetcher
from utils.logger import get_logger


logger = get_logger(__name__)


class Collector:
    def __init__(self, fetchers=None):
        self.fetchers = fetchers or [RSSFetcher()]

    async def collect(self, interests: list[str], limit: int) -> list[SourceItem]:
        if limit <= 0:
            return []

        per_fetcher_limit = max(1, limit)
        results = await asyncio.gather(
            *(fetcher.fetch(interests, per_fetcher_limit) for fetcher in self.fetchers),
            return_exceptions=True,
        )

        items: list[SourceItem] = []
        for result in results:
            if isinstance(result, Exception):
                logger.exception("Source fetcher failed", exc_info=result)
                continue
            items.extend(result)
        logger.info("Collected raw items count=%s", len(items))
        return items
