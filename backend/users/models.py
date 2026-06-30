from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class User:
    user_id: str
    nickname: str | None = None
    interests: list[str] = field(default_factory=list)
    subscription_plan: str = "free"
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
