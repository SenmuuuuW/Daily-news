from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class SourceItem:
    title: str
    url: str
    source: str
    summary: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
