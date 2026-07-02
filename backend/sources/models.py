from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceItem:
    title: str
    content: str
    url: str
    source: str
    source_url: str | None = None
    published_at: datetime | None = None
    category: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    matched_topics: list[str] = field(default_factory=list)
    score: float = 0.0
    raw_score: float = 0.0
    rank_reason: str | None = None

    @property
    def summary(self) -> str:
        return self.content

    @summary.setter
    def summary(self, value: str | None) -> None:
        self.content = value or ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "category": self.category,
            "matched_topics": self.matched_topics,
            "raw_score": self.raw_score,
        }
