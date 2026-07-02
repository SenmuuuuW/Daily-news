from __future__ import annotations

from difflib import SequenceMatcher
import re
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sources.models import SourceItem


def clean_items(items: list[SourceItem]) -> list[SourceItem]:
    cleaned: list[SourceItem] = []
    seen_urls: dict[str, int] = {}
    seen_titles: dict[str, int] = {}

    for item in items:
        title = _clean_text(item.title)
        content = _clean_text(item.content or "")
        url = _normalize_url(item.url)
        title_key = _normalize_title(title)
        url_key = _url_key(url)

        if not title or not url:
            continue

        item.title = title
        item.content = content
        item.url = url

        duplicate_index = seen_urls.get(url_key)
        if duplicate_index is None:
            duplicate_index = seen_titles.get(title_key)
        if duplicate_index is None:
            duplicate_index = _find_similar_title(cleaned, title_key)

        if duplicate_index is not None:
            best = _best_item(cleaned[duplicate_index], item)
            cleaned[duplicate_index] = best
            seen_urls[url_key] = duplicate_index
            seen_titles[title_key] = duplicate_index
            continue

        seen_urls[url_key] = len(cleaned)
        seen_titles[title_key] = len(cleaned)
        cleaned.append(item)

    return cleaned


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_url(value: str) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    query_pairs = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _url_key(value: str) -> str:
    parsed = urlparse(value)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, ""))


def _normalize_title(value: str) -> str:
    value = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def _find_similar_title(items: list[SourceItem], title_key: str) -> int | None:
    if not title_key:
        return None
    for index, existing in enumerate(items):
        existing_key = _normalize_title(existing.title)
        if existing_key and SequenceMatcher(None, existing_key, title_key).ratio() >= 0.96:
            return index
    return None


def _best_item(first: SourceItem, second: SourceItem) -> SourceItem:
    return first if _quality_score(first) >= _quality_score(second) else second


def _quality_score(item: SourceItem) -> float:
    score = 0.0
    if item.content:
        score += min(len(item.content), 300) / 100
    if item.published_at:
        score += 2
    score += len(item.matched_topics) * 2
    if item.source_url:
        score += 0.5
    return score
