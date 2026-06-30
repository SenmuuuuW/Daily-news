from functools import lru_cache

from config import settings
from storage.cache import PlanConfigCache
from users.models import User
from users.repository import UserRepository


class UserService:
    def __init__(
        self,
        repository: UserRepository | None = None,
        plan_cache: PlanConfigCache | None = None,
    ):
        self.repository = repository or UserRepository()
        self.plan_cache = plan_cache or PlanConfigCache()

    def create_user(
        self,
        user_id: str,
        nickname: str | None = None,
        subscription_plan: str | None = None,
    ) -> User:
        user = User(
            user_id=user_id,
            nickname=nickname,
            subscription_plan=subscription_plan or settings.default_plan,
        )
        return self.repository.upsert(user)

    def upsert_interests(
        self,
        user_id: str,
        interests: list[str],
        nickname: str | None = None,
    ) -> User:
        existing = self.repository.get(user_id)
        user = existing or User(user_id=user_id, subscription_plan=settings.default_plan)
        user.nickname = nickname or user.nickname
        user.interests = _merge_interests(user.interests, interests)
        plan = self.plan_cache.get_plan(user.subscription_plan)
        user.interests = user.interests[: plan.max_interest_topics]
        return self.repository.upsert(user)

    def update_subscription_plan(self, user_id: str, subscription_plan: str) -> User:
        user = self.repository.get(user_id) or User(user_id=user_id)
        user.subscription_plan = subscription_plan
        return self.repository.upsert(user)

    def set_enabled(self, user_id: str, enabled: bool) -> User | None:
        return self.repository.set_enabled(user_id, enabled)

    def list_active_users(self) -> list[User]:
        return self.repository.list_active()


def _merge_interests(existing: list[str], incoming: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for interest in [*existing, *incoming]:
        normalized = interest.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            merged.append(normalized)
    return merged


@lru_cache
def get_user_service() -> UserService:
    return UserService()
