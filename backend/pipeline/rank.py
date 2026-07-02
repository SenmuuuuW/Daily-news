from __future__ import annotations

from datetime import datetime, timezone

from sources.models import SourceItem


def rank_items(items: list[SourceItem], interests: list[str], limit: int) -> list[SourceItem]:
    topic_keys = [topic.casefold() for topic in interests]

    def score(item: SourceItem) -> float:
        text = f"{item.title} {item.content or ''} {item.category or ''}".casefold()
        topic_score = sum(10 for topic in topic_keys if topic in text)
        source_score = item.score / 1000 if item.score else 0
        return topic_score + source_score

    for item in items:
        item.score = score(item)

    return sorted(
        items,
        key=lambda item: (-item.score, item.source, item.title.casefold()),
    )[:limit]


def _recency_score(published_at: datetime | None) -> float:
    if not published_at:
        return 0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(1, (now - published_at).total_seconds() / 3600)
    return max(0, 3 - age_hours / 24)
