from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from config import settings
from utils.logger import get_logger


logger = get_logger(__name__)
WXPUSHER_SEND_URL = "https://wxpusher.zjiecode.com/api/send/message"
WXPUSHER_SUCCESS_CODE = 1000


@dataclass
class DeliveryResult:
    ok: bool
    provider: str
    status_code: int | None
    message: str
    response_text: str | None = None


async def send_wechat_push(title: str, content: str) -> DeliveryResult:
    provider = settings.wechat_push_provider.strip().lower() or "wxpusher"
    if provider != "wxpusher":
        return DeliveryResult(
            ok=False,
            provider=provider,
            status_code=None,
            message=f"Unsupported WeChat push provider: {provider}",
        )

    return await _send_wxpusher(title=title, content=content)


async def _send_wxpusher(title: str, content: str) -> DeliveryResult:
    app_token = settings.wxpusher_app_token
    uids = settings.wxpusher_uids
    topic_ids = settings.wxpusher_topic_ids

    if not app_token or app_token == "replace-me":
        return DeliveryResult(
            ok=False,
            provider="wxpusher",
            status_code=None,
            message="WxPusher app token is not configured.",
        )
    if not uids and not topic_ids:
        return DeliveryResult(
            ok=False,
            provider="wxpusher",
            status_code=None,
            message="WxPusher UID or topic ID is not configured.",
        )

    payload = _build_wxpusher_payload(
        app_token=app_token,
        title=title,
        content=content,
        uids=uids,
        topic_ids=topic_ids,
    )

    try:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.post(WXPUSHER_SEND_URL, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("WxPusher request failed: %s", type(exc).__name__)
        return DeliveryResult(
            ok=False,
            provider="wxpusher",
            status_code=None,
            message=f"WxPusher request failed: {type(exc).__name__}",
        )

    response_text = response.text
    if response.status_code >= 400:
        return DeliveryResult(
            ok=False,
            provider="wxpusher",
            status_code=response.status_code,
            message=f"WxPusher HTTP error: {response.status_code}",
            response_text=response_text,
        )

    return _parse_wxpusher_response(response.status_code, response_text)


def _build_wxpusher_payload(
    app_token: str,
    title: str,
    content: str,
    uids: list[str],
    topic_ids: list[int],
) -> dict[str, Any]:
    # WxPusher message API currently accepts appToken, content, summary,
    # contentType, uids, and topicIds. If the provider changes its API,
    # keep the adjustment isolated in this function.
    payload: dict[str, Any] = {
        "appToken": app_token,
        "content": content,
        "summary": title[:99],
        "contentType": 1,
    }
    if uids:
        payload["uids"] = uids
    if topic_ids:
        payload["topicIds"] = topic_ids
    return payload


def _parse_wxpusher_response(status_code: int, response_text: str) -> DeliveryResult:
    try:
        data = httpx.Response(status_code=status_code, text=response_text).json()
    except ValueError:
        return DeliveryResult(
            ok=False,
            provider="wxpusher",
            status_code=status_code,
            message="WxPusher response was not JSON.",
            response_text=response_text,
        )

    code = data.get("code")
    success = data.get("success")
    message = str(data.get("msg") or data.get("message") or "")
    ok = success is True or code == WXPUSHER_SUCCESS_CODE
    if ok:
        return DeliveryResult(
            ok=True,
            provider="wxpusher",
            status_code=status_code,
            message=message or "WxPusher send succeeded.",
            response_text=response_text,
        )

    return DeliveryResult(
        ok=False,
        provider="wxpusher",
        status_code=status_code,
        message=message or f"WxPusher returned error code: {code}",
        response_text=response_text,
    )
