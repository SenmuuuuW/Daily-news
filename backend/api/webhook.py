from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from config import settings
from users.service import UserService, get_user_service
from utils.logger import get_logger

router = APIRouter(tags=["wecom-webhook"])
logger = get_logger(__name__)


@router.post("/webhook/wecom")
async def receive_wecom_message(
    request: Request,
    x_wecom_token: Optional[str] = Header(default=None),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    if settings.wecom_incoming_token and x_wecom_token != settings.wecom_incoming_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()
    user_id = _extract_user_id(payload)
    nickname = _extract_nickname(payload)
    interests = _extract_interests(payload)

    if not user_id:
        raise HTTPException(status_code=400, detail="Unable to identify WeCom user")
    if not interests:
        return {"ok": True, "message": "No interests detected"}

    user = user_service.upsert_interests(
        user_id=user_id,
        nickname=nickname,
        interests=interests,
    )
    logger.info("Updated interests for user_id=%s topics=%s", user.user_id, interests)
    return {"ok": True, "user_id": user.user_id, "interests": user.interests}


def _extract_user_id(payload: dict[str, Any]) -> str | None:
    return (
        payload.get("FromUserName")
        or payload.get("from_user")
        or payload.get("user_id")
        or payload.get("userid")
    )


def _extract_nickname(payload: dict[str, Any]) -> str | None:
    return payload.get("nickname") or payload.get("user_name") or payload.get("name")


def _extract_interests(payload: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("Content")
        or payload.get("content")
        or payload.get("text")
        or payload.get("message")
        or ""
    )
    if isinstance(raw, list):
        values = raw
    else:
        normalized = str(raw).replace("，", ",").replace("\n", ",")
        values = [part.strip() for part in normalized.split(",")]
    return [value for value in values if value]
