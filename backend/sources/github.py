from urllib.parse import quote_plus

from sources.models import SourceItem
from utils.http import HTTPClient


class GitHubTrendingFetcher:
    source_name = "github"

    def __init__(self, http_client: HTTPClient | None = None):
        self.http_client = http_client or HTTPClient()

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        items: list[SourceItem] = []
        per_topic_limit = max(1, limit // max(1, len(topics)))

        for topic in topics:
            query = quote_plus(topic)
            data = await self.http_client.get_json(
                f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={per_topic_limit}"
            )
            for repo in data.get("items", []):
                items.append(
                    SourceItem(
                        title=repo.get("full_name", ""),
                        url=repo.get("html_url", ""),
                        source=self.source_name,
                        summary=repo.get("description"),
                        author=repo.get("owner", {}).get("login"),
                        tags=[topic],
                        score=float(repo.get("stargazers_count") or 0),
                    )
                )
                if len(items) >= limit:
                    return items
        return items
