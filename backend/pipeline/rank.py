from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from sources.models import SourceItem


def rank_items(
    items: list[SourceItem],
    interests: list[str],
    limit: int,
    exclusions: list[str] | None = None,
    min_score: float | None = None,
) -> list[SourceItem]:
    if limit <= 0:
        return []

    topics = [topic.strip() for topic in interests if topic.strip()]
    topic_keys = [(topic, topic.casefold()) for topic in topics]
    exclusion_keys = [(value.strip(), value.strip().casefold()) for value in (exclusions or []) if value.strip()]

    def score(item: SourceItem) -> float:
        text = f"{item.title} {item.content or ''} {item.category or ''}".casefold()
        title = item.title.casefold()
        content = (item.content or "").casefold()

        score_value = 0.0
        reasons: list[str] = []

        title_matches = [topic for topic, key in topic_keys if key and key in title]
        summary_matches = [topic for topic, key in topic_keys if key and key in content]
        matched_topics = sorted(set(item.matched_topics or title_matches + summary_matches), key=str.casefold)
        item.matched_topics = matched_topics

        if title_matches:
            boost = 12 * len(set(title_matches))
            score_value += boost
            reasons.append(f"matched topic in title: {', '.join(sorted(set(title_matches), key=str.casefold))} (+{boost:g})")
        if summary_matches:
            boost = 6 * len(set(summary_matches))
            score_value += boost
            reasons.append(f"matched topic in summary: {', '.join(sorted(set(summary_matches), key=str.casefold))} (+{boost:g})")
        phrase_matches = [topic for topic in matched_topics if " " in topic.strip()]
        if phrase_matches:
            boost = 4 * len(phrase_matches)
            score_value += boost
            reasons.append(f"phrase match boost: {', '.join(phrase_matches)} (+{boost:g})")
        if len(matched_topics) > 1:
            boost = 3 * (len(matched_topics) - 1)
            score_value += boost
            reasons.append(f"multi-topic match boost: {len(matched_topics)} topics (+{boost:g})")
        if not topic_keys and text:
            score_value += 2
            reasons.append("general RSS item (+2)")

        excluded_terms = [value for value, key in exclusion_keys if key and key in text]
        if excluded_terms:
            penalty = 15 * len(set(excluded_terms))
            score_value -= penalty
            reasons.append(
                f"excluded keyword penalty: {', '.join(sorted(set(excluded_terms), key=str.casefold))} (-{penalty:g})"
            )

        recency = _recency_score(item.published_at)
        if recency:
            score_value += recency
            reasons.append(f"recent item boost (+{recency:g})")

        age_penalty = _age_penalty(item.published_at)
        if age_penalty:
            score_value -= age_penalty
            reasons.append(f"stale published_at penalty (-{age_penalty:g})")

        if _trusted_source(item):
            score_value += 1.5
            reasons.append("trusted/official source boost (+1.5)")

        if not item.content:
            score_value -= 2
            reasons.append("missing summary penalty (-2)")

        if item.raw_score:
            score_value += min(item.raw_score, 5)
            reasons.append(f"source match score (+{min(item.raw_score, 5):g})")

        item.rank_reason = ", ".join(reasons) if reasons else "baseline"
        item.raw_score = item.raw_score or score_value
        return score_value

    for item in items:
        item.score = score(item)

    ranked = sorted(
        items,
        key=lambda item: (-item.score, item.source, item.title.casefold()),
    )
    if min_score is not None:
        ranked = [item for item in ranked if item.score >= min_score]
    return ranked[:limit]


def _recency_score(published_at: datetime | None) -> float:
    if not published_at:
        return 0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(1, (now - published_at).total_seconds() / 3600)
    return max(0, 5 - age_hours / 24)


def _age_penalty(published_at: datetime | None) -> float:
    if not published_at:
        return 0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = max(0, (now - published_at).total_seconds() / 86400)
    if age_days <= 14:
        return 0
    return min(40, (age_days - 14) / 7)


def _trusted_source(item: SourceItem) -> bool:
    feed_url = item.source_url or item.url
    host = urlparse(feed_url).netloc.casefold()
    return any(
        signal in host
        for signal in (
            ".gov",
            ".edu",
            "arxiv.org",
            "github.blog",
            "openai.com",
            "googleblog.com",
            "microsoft.com",
            "apple.com",
        )
    )
