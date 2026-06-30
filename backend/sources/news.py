from sources.models import SourceItem


class NewsFetcher:
    source_name = "news"

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        # Placeholder for future news/API integrations.
        return []
