from __future__ import annotations

import asyncio

from config import settings
from delivery.wecom_external import get_wecom_access_token, validate_wecom_external_config
from utils.logger import configure_logging


async def main() -> int:
    configure_logging(settings.log_level)
    target_type = settings.wecom_external_target_type
    print("WeCom External Contact / Customer Group Config Check")
    print(f"target_type: {target_type}")
    print(f"enabled: {settings.wecom_external_enabled}")
    print(f"dry_run: {settings.wecom_external_dry_run}")

    readiness = validate_wecom_external_config(target_type)
    if readiness.ok:
        print("config readiness: OK")
    else:
        print(f"config readiness: NOT READY - {readiness.message}")

    target_ready = _target_ready(target_type)
    print(f"target readiness: {'OK' if target_ready else 'NOT READY'}")

    if settings.wecom_corp_id and settings.wecom_external_contact_secret:
        token_result = await get_wecom_access_token(
            corp_id=settings.wecom_corp_id,
            secret=settings.wecom_external_contact_secret,
        )
        print(f"token fetch: {'OK' if token_result.ok else 'FAILED'} - {token_result.message}")
    else:
        print("token fetch: SKIPPED - corp_id or external contact secret is missing")

    print("next command:")
    print(
        "CONFIRM_WECOM_EXTERNAL_SEND=YES DAILY_DIGEST_WECOM_EXTERNAL_ENABLED=true "
        "python -m scripts.run_rss_profile --profile ai_tech --send-wecom-external"
    )
    return 0 if readiness.ok else 1


def _target_ready(target_type: str) -> bool:
    normalized = target_type.strip().lower()
    if normalized == "customer":
        return bool(settings.wecom_external_userids)
    if normalized == "customer_group":
        return bool(settings.wecom_customer_group_chat_ids)
    return False


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
