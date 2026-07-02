from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceItem:
    title: str
    content: str
    url: str
    source: str
    published_at: datetime | None = None
    category: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    score: float = 0.0

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
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "category": self.category,
        }
