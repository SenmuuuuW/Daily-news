from __future__ import annotations

from abc import ABC, abstractmethod

from sources.models import SourceItem


class SummarizerProvider(ABC):
    @abstractmethod
    async def summarize(
        self,
        interests: list[str],
        items: list[SourceItem],
        summary_length: str,
        advanced_analysis_enabled: bool,
    ) -> str:
        raise NotImplementedError


class MockSummarizer(SummarizerProvider):
    async def summarize(
        self,
        interests: list[str],
        items: list[SourceItem],
        summary_length: str,
        advanced_analysis_enabled: bool,
    ) -> str:
        if not items:
            return "今天没有找到足够相关的新内容。"

        max_items = {"short": 3, "medium": 5, "long": 8}.get(summary_length, 3)
        lines = [f"围绕 {', '.join(interests)}，今天值得关注："]
        for index, item in enumerate(items[:max_items], start=1):
            detail = f" - {item.content[:90]}..." if item.content else ""
            lines.append(f"{index}. {item.title}{detail}")
        if advanced_analysis_enabled:
            lines.append("进阶观察：相关内容可继续按来源可信度和主题热度扩展分析。")
        return "\n".join(lines)
