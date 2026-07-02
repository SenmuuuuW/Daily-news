from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus

from sources.models import SourceItem
from utils.http import HTTPClient


class ArxivFetcher:
    source_name = "arxiv"
    namespace = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, http_client: HTTPClient | None = None):
        self.http_client = http_client or HTTPClient()

    async def fetch(self, topics: list[str], limit: int) -> list[SourceItem]:
        if not topics:
            return []
        query = "+OR+".join(f"all:{quote_plus(topic)}" for topic in topics)
        url = (
            "https://export.arxiv.org/api/query"
            f"?search_query={query}&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
        )
        xml_text = await self.http_client.get_text(url)
        root = ET.fromstring(xml_text)

        items: list[SourceItem] = []
        for entry in root.findall("atom:entry", self.namespace):
            title = _text(entry, "atom:title")
            url = _text(entry, "atom:id")
            summary = _text(entry, "atom:summary")
            published = _text(entry, "atom:published")
            items.append(
                SourceItem(
                    title=" ".join(title.split()),
                    content=" ".join(summary.split()),
                    url=url,
                    source=self.source_name,
                    published_at=_parse_datetime(published),
                    category=topics[0] if topics else None,
                    tags=topics,
                )
            )
        return items


def _text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ArxivFetcher.namespace)
    return node.text if node is not None and node.text else ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
