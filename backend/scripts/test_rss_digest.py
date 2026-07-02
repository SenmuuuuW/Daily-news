from __future__ import annotations

import asyncio
import os

from scheduler.daily_job import DailyDigestJob
from storage.db import init_db
from users.service import UserService
from utils.logger import configure_logging


def _topics_from_env() -> list[str]:
    raw = os.getenv("DAILY_DIGEST_TEST_TOPICS", "AI, technology")
    return [topic.strip() for topic in raw.replace("，", ",").split(",") if topic.strip()]


async def main() -> None:
    configure_logging(os.getenv("DAILY_DIGEST_LOG_LEVEL", "INFO"))
    init_db()

    user_id = os.getenv("DAILY_DIGEST_TEST_USER_ID", "local_rss_test_user")
    topics = _topics_from_env()
    user_service = UserService()
    user_service.upsert_interests(user_id=user_id, nickname="Local RSS Test", interests=topics)

    await DailyDigestJob(user_service=user_service).run()


if __name__ == "__main__":
    asyncio.run(main())
