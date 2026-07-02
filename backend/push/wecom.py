from __future__ import annotations

from typing import Any

import httpx

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class WeComPushClient:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or settings.wecom_push_webhook_url

    async def send_text(self, user_id: str, content: str) -> bool:
        if not self.webhook_url or "replace-me" in self.webhook_url:
            logger.info("WeCom webhook is not configured; printing digest for user_id=%s", user_id)
            print("\n========== MOCK WECOM MESSAGE ==========")
            print(f"To: {user_id}")
            print(content)
            print("========== END MOCK WECOM MESSAGE ==========\n")
            return True

        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
            },
        }
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
        if not _wecom_response_ok(response):
            return False
        logger.info("WeCom push succeeded for user_id=%s", user_id)
        return True


def _wecom_response_ok(response: httpx.Response) -> bool:
    try:
        data: dict[str, Any] = response.json()
    except ValueError:
        logger.warning("WeCom response was not JSON; HTTP status=%s", response.status_code)
        return False

    errcode = data.get("errcode")
    if errcode in (None, 0):
        return True

    logger.warning(
        "WeCom push failed errcode=%s errmsg=%s",
        errcode,
        data.get("errmsg", ""),
    )
    return False
