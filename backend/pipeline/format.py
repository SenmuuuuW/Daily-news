from datetime import datetime

from sources.models import SourceItem
from users.models import User


def format_wecom_digest(user: User, summary: str, items: list[SourceItem]) -> str:
    date_label = datetime.now().strftime("%Y-%m-%d")
    nickname = user.nickname or user.user_id
    lines = [
        f"早上好，{nickname}",
        f"你的每日兴趣摘要 - {date_label}",
        "",
        summary,
        "",
        "精选链接：",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"   {item.url}")

    lines.append("")
    lines.append("回复新的兴趣关键词，可继续更新订阅主题。")
    return "\n".join(lines)
