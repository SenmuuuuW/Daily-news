import httpx

from config import settings


class HTTPClient:
    async def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
