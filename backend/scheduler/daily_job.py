from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from pipeline.clean import clean_items
from pipeline.collect import Collector
from pipeline.format import format_wecom_digest
from pipeline.rank import rank_items
from pipeline.summarize import MockSummarizer, SummarizerProvider
from push.wecom import WeComPushClient
from storage.logs import DigestLogRepository
from storage.db import init_db
from storage.cache import PlanConfigCache
from users.service import UserService
from utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


class DailyDigestJob:
    def __init__(
        self,
        user_service: UserService | None = None,
        collector: Collector | None = None,
        summarizer: SummarizerProvider | None = None,
        push_client: WeComPushClient | None = None,
    ):
        self.user_service = user_service or UserService()
        self.collector = collector or Collector()
        self.summarizer = summarizer or MockSummarizer()
        self.push_client = push_client or WeComPushClient()
        self.plan_cache = PlanConfigCache()
        self.log_repository = DigestLogRepository()

    async def run(self) -> None:
        users = self.user_service.list_active_users()
        logger.info("Starting daily digest job for %s active users", len(users))
        if not users:
            logger.info("No active users found; nothing to send")
            return

        for user in users:
            plan = self.plan_cache.get_plan(user.subscription_plan)
            interests = user.interests[: plan.max_interest_topics]
            if not interests:
                logger.info("Skipping user_id=%s because no interests are configured", user.user_id)
                continue
            try:
                logger.info("Building digest for user_id=%s interests=%s", user.user_id, interests)
                collected = await self.collector.collect(interests, plan.collected_items)
                cleaned = clean_items(collected)
                ranked = rank_items(cleaned, interests, plan.collected_items)
                summary = await self.summarizer.summarize(
                    interests=interests,
                    items=ranked,
                    summary_length=plan.summary_length,
                    advanced_analysis_enabled=plan.advanced_analysis_enabled,
                )
                message = format_wecom_digest(user, summary, ranked)
                sent = await self.push_client.send_text(user.user_id, message)
                self.log_repository.save(
                    user_id=user.user_id,
                    status="sent" if sent else "skipped",
                    item_count=len(ranked),
                    message=message,
                )
                logger.info(
                    "Digest finished for user_id=%s status=%s item_count=%s",
                    user.user_id,
                    "sent" if sent else "skipped",
                    len(ranked),
                )
            except Exception as exc:
                logger.exception("Digest failed for user_id=%s", user.user_id)
                self.log_repository.save(
                    user_id=user.user_id,
                    status="failed",
                    item_count=0,
                    message=str(exc),
                )


def create_scheduler(job: DailyDigestJob | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    digest_job = job or DailyDigestJob()
    scheduler.add_job(
        digest_job.run,
        CronTrigger(hour=settings.digest_hour, minute=settings.digest_minute),
        id="daily_digest",
        replace_existing=True,
    )
    return scheduler


async def main() -> None:
    configure_logging(settings.log_level)
    init_db()
    await DailyDigestJob().run()


if __name__ == "__main__":
    asyncio.run(main())
