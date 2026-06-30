import httpx

from config import settings


class WeComPushClient:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or settings.wecom_push_webhook_url

    async def send_text(self, user_id: str, content: str) -> bool:
        if not self.webhook_url:
            return False

        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": [user_id],
            },
        }
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
        return True
