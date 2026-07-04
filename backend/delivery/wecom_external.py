from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from config import settings
from utils.logger import get_logger


logger = get_logger(__name__)
PROVIDER = "wecom_external"
TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
ADD_MSG_TEMPLATE_URL = "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_msg_template"
VALID_TARGET_TYPES = {"customer", "customer_group"}


@dataclass
class DeliveryResult:
    ok: bool
    provider: str
    status_code: int | None
    message: str
    response_text: str | None = None
    raw: dict | None = None


async def get_wecom_access_token(corp_id: str, secret: str) -> DeliveryResult:
    if not corp_id:
        return DeliveryResult(False, PROVIDER, None, "WeCom corp_id is not configured.")
    if not secret:
        return DeliveryResult(False, PROVIDER, None, "WeCom external contact secret is not configured.")

    url = f"{TOKEN_URL}?corpid={quote(corp_id)}&corpsecret={quote(secret)}"
    try:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("WeCom access token request failed: %s", type(exc).__name__)
        return DeliveryResult(False, PROVIDER, None, f"WeCom token request failed: {type(exc).__name__}")

    parsed = _parse_json_response(response)
    if not parsed.ok:
        return parsed

    data = parsed.raw or {}
    errcode = data.get("errcode")
    if errcode not in (None, 0):
        return DeliveryResult(False, PROVIDER, response.status_code, _wecom_error_message(data), response.text, data)

    access_token = data.get("access_token")
    if not access_token:
        return DeliveryResult(False, PROVIDER, response.status_code, "WeCom token response did not include access_token.", response.text, data)

    return DeliveryResult(True, PROVIDER, response.status_code, "WeCom access token fetched.", response.text, data)


async def send_wecom_external_text(title: str, content: str, target_type: str) -> DeliveryResult:
    normalized_target_type = (target_type or settings.wecom_external_target_type).strip().lower()
    readiness = validate_wecom_external_config(normalized_target_type)
    if not readiness.ok:
        return readiness

    if settings.wecom_external_dry_run:
        return DeliveryResult(
            ok=False,
            provider=PROVIDER,
            status_code=None,
            message="WeCom external dry run is enabled; no API send was attempted.",
            raw={"target_type": normalized_target_type},
        )

    token_result = await get_wecom_access_token(
        corp_id=settings.wecom_corp_id or "",
        secret=settings.wecom_external_contact_secret or "",
    )
    if not token_result.ok:
        return token_result

    access_token = (token_result.raw or {}).get("access_token")
    if not access_token:
        return DeliveryResult(False, PROVIDER, token_result.status_code, "WeCom access token missing after successful token call.", token_result.response_text, token_result.raw)

    payload = _build_add_msg_template_payload(title=title, content=content, target_type=normalized_target_type)
    url = f"{ADD_MSG_TEMPLATE_URL}?access_token={quote(access_token)}"
    try:
        async with httpx.AsyncClient(timeout=settings.wecom_request_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("WeCom external send request failed: %s", type(exc).__name__)
        return DeliveryResult(False, PROVIDER, None, f"WeCom external send request failed: {type(exc).__name__}")

    parsed = _parse_json_response(response)
    if not parsed.ok:
        return parsed

    data = parsed.raw or {}
    errcode = data.get("errcode")
    if errcode != 0:
        return DeliveryResult(False, PROVIDER, response.status_code, _wecom_error_message(data), response.text, data)

    msgid = data.get("msgid") or data.get("fail_list") or ""
    return DeliveryResult(
        ok=True,
        provider=PROVIDER,
        status_code=response.status_code,
        message=(
            "WeCom external group-send task created. Depending on account settings, "
            "the sending employee may still need to confirm delivery in WeCom."
            + (f" msgid={msgid}" if msgid else "")
        ),
        response_text=response.text,
        raw=data,
    )


def validate_wecom_external_config(target_type: str | None = None) -> DeliveryResult:
    normalized_target_type = (target_type or settings.wecom_external_target_type).strip().lower()
    reasons = []
    if normalized_target_type not in VALID_TARGET_TYPES:
        reasons.append(f"target_type must be one of {sorted(VALID_TARGET_TYPES)}")
    if not settings.wecom_corp_id:
        reasons.append("DAILY_DIGEST_WECOM_CORP_ID is not set")
    if not settings.wecom_external_contact_secret:
        reasons.append("DAILY_DIGEST_WECOM_EXTERNAL_CONTACT_SECRET is not set")
    if not settings.wecom_sender_userid:
        reasons.append("DAILY_DIGEST_WECOM_SENDER_USERID is not set")
    if normalized_target_type == "customer" and not settings.wecom_external_userids:
        reasons.append("DAILY_DIGEST_WECOM_EXTERNAL_USERIDS is not set")
    if normalized_target_type == "customer_group" and not settings.wecom_customer_group_chat_ids:
        reasons.append("DAILY_DIGEST_WECOM_CUSTOMER_GROUP_CHAT_IDS is not set")

    if reasons:
        return DeliveryResult(False, PROVIDER, None, "; ".join(reasons), raw={"target_type": normalized_target_type, "reasons": reasons})

    return DeliveryResult(True, PROVIDER, None, "WeCom external config looks ready.", raw={"target_type": normalized_target_type})


def _build_add_msg_template_payload(title: str, content: str, target_type: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_type": "single" if target_type == "customer" else "group",
        "sender": settings.wecom_sender_userid,
        "text": {"content": f"{title}\n\n{content}"},
        "attachments": [],
    }

    if target_type == "customer":
        payload["external_userid"] = settings.wecom_external_userids
    else:
        payload["chat_id_list"] = settings.wecom_customer_group_chat_ids

    # TODO: Verify this payload against the enterprise's customer-contact API
    # permissions during the first real account test. Some WeCom account setups
    # create a group-send task that the sender must confirm in WeCom rather than
    # directly delivering the message.
    return payload


def _parse_json_response(response: httpx.Response) -> DeliveryResult:
    response_text = response.text
    if response.status_code >= 400:
        return DeliveryResult(False, PROVIDER, response.status_code, f"WeCom HTTP error: {response.status_code}", response_text)

    try:
        data = response.json()
    except ValueError:
        return DeliveryResult(False, PROVIDER, response.status_code, "WeCom response was not JSON.", response_text)

    return DeliveryResult(True, PROVIDER, response.status_code, "WeCom response parsed.", response_text, data)


def _wecom_error_message(data: dict[str, Any]) -> str:
    return f"WeCom API error errcode={data.get('errcode')} errmsg={data.get('errmsg', '')}"
