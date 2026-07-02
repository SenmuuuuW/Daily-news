from __future__ import annotations

from datetime import datetime

from pipeline.summarize import summarize_item
from sources.models import SourceItem
from users.models import User


def format_wecom_digest(user: User, summary: str, items: list[SourceItem]) -> str:
    date_label = datetime.now().strftime("%Y-%m-%d")
    lines = [f"【Daily Intelligence Brief｜{date_label}】", ""]

    if not items:
        lines.extend(
            [
                "今日未从配置的 RSS 来源中发现足够相关的新信息。",
                "",
                "说明：本简报基于公开 RSS / 授权公开来源自动整理，建议点击原文核对细节。",
            ]
        )
        return "\n".join(lines)

    lines.append(f"今日为你筛选到 {len(items)} 条值得关注的信息：")
    lines.append("")

    for index, item in enumerate(items, start=1):
        category = item.category or _category_from_topics(item)
        source = item.source or _source_from_url(item)
        lines.extend(
            [
                f"{index}. {item.title}",
                f"分类：{category}",
                f"摘要：{summarize_item(item, max_chars=120)}",
                f"来源：{source}",
                f"链接：{item.url}",
                "",
            ]
        )

    lines.append("今日观察：")
    lines.extend(_observations(summary, items))
    lines.append("")
    lines.append("说明：本简报基于公开 RSS / 授权公开来源自动整理，建议点击原文核对细节。")
    return "\n".join(lines)


def _category_from_topics(item: SourceItem) -> str:
    if item.matched_topics:
        return "、".join(item.matched_topics[:3])
    if item.tags:
        return "、".join(item.tags[:3])
    return "General"


def _source_from_url(item: SourceItem) -> str:
    return item.source_url or item.url


def _observations(summary: str, items: list[SourceItem]) -> list[str]:
    matched_topics = sorted({topic for item in items for topic in item.matched_topics}, key=str.casefold)
    observations = []
    if matched_topics:
        observations.append(f"- 相关主题集中在：{'、'.join(matched_topics[:5])}。")
    if any(item.published_at for item in items):
        observations.append("- 已优先考虑近期发布的信息。")
    if any(item.rank_reason for item in items):
        observations.append("- 排序依据包括关键词匹配、发布时间、来源可信度和摘要完整度。")
    if not observations and summary:
        observations.append(f"- {summary.splitlines()[0][:80]}")
    return observations or ["- 建议打开原文核对关键事实后再采取行动。"]
