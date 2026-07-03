from __future__ import annotations

import httpx

from config import settings

DEFAULT_HEADERS = {
    "User-Agent": "DailyWeComDigestBot/0.1 (+https://github.com/SenmuuuuW/Daily-news)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/plain, */*",
}


class HTTPClient:
    async def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.get(url, headers=_merge_headers(headers))
            response.raise_for_status()
            return response.json()

    async def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.get(url, headers=_merge_headers(headers))
            response.raise_for_status()
            return response.text


def _merge_headers(headers: dict[str, str] | None) -> dict[str, str]:
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    return merged
