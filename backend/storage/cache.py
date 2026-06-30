from dataclasses import dataclass

import yaml

from config import settings


@dataclass(slots=True)
class PlanConfig:
    name: str
    max_interest_topics: int
    collected_items: int
    summary_length: str
    advanced_analysis_enabled: bool


class PlanConfigCache:
    def __init__(self):
        self._cache: dict[str, PlanConfig] = {}

    def get_plan(self, name: str) -> PlanConfig:
        if name not in self._cache:
            self._cache[name] = self._load_plan(name)
        return self._cache[name]

    def _load_plan(self, name: str) -> PlanConfig:
        path = settings.plan_dir / f"{name}.yaml"
        if not path.exists():
            path = settings.plan_dir / f"{settings.default_plan}.yaml"

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return PlanConfig(
            name=data["name"],
            max_interest_topics=int(data["max_interest_topics"]),
            collected_items=int(data["collected_items"]),
            summary_length=str(data["summary_length"]),
            advanced_analysis_enabled=bool(data["advanced_analysis_enabled"]),
        )
