import re
from html import unescape

from sources.models import SourceItem


def clean_items(items: list[SourceItem]) -> list[SourceItem]:
    cleaned: list[SourceItem] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for item in items:
        title = _clean_text(item.title)
        summary = _clean_text(item.summary or "")
        title_key = title.casefold()
        url_key = item.url.strip()

        if not title or not url_key:
            continue
        if url_key in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url_key)
        seen_titles.add(title_key)
        item.title = title
        item.summary = summary
        item.url = url_key
        cleaned.append(item)
    return cleaned


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()
