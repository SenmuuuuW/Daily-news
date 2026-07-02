from __future__ import annotations

from abc import ABC, abstractmethod
import re
from html import unescape

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
            return "今日未从配置的 RSS 来源中发现足够相关的新信息。"

        max_items = {"short": 3, "medium": 5, "long": 8}.get(summary_length, 3)
        topic_label = "、".join(interests) if interests else "已配置 RSS 来源"
        lines = [f"围绕 {topic_label}，今天值得关注："]
        for index, item in enumerate(items[:max_items], start=1):
            lines.append(f"{index}. {item.title}：{summarize_item(item, max_chars=80)}")
        if advanced_analysis_enabled:
            lines.append("进阶观察：优先核对高相关、近期发布且来自官方/可信来源的信息。")
        return "\n".join(lines)


def summarize_item(item: SourceItem, max_chars: int = 120) -> str:
    text = _clean_text(item.content)
    if not text:
        text = f"可点击原文查看 {item.title} 的详细信息。"
    return _truncate(text, max_chars)


def _clean_text(value: str | None) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)].rstrip() + "…"
