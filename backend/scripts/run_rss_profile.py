from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from config import BASE_DIR, settings
from delivery.wechat_push import send_wechat_push
from pipeline.clean import dedupe_items, normalize_items
from pipeline.format import format_wecom_digest
from pipeline.rank import rank_items
from pipeline.summarize import MockSummarizer
from push.wecom import WeComPushClient
from sources.models import SourceItem
from sources.rss import RSSFetcher
from users.models import User
from utils.logger import configure_logging


DEFAULT_PROFILE_PATH = BASE_DIR / "config_profiles" / "rss_test_profiles.yaml"
DEFAULT_OUTPUT_DIR = Path("outputs/rss_tests")


@dataclass
class RSSProfile:
    name: str
    description: str
    rss_feeds: list[str]
    topics: list[str]
    exclusions: list[str]
    max_items: int
    min_score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local RSS profile test without sending by default.")
    parser.add_argument("--profile", required=True, help="Profile name, for example ai_tech")
    parser.add_argument("--limit", type=int, default=None, help="Override profile max_items")
    parser.add_argument("--send-wecom", action="store_true", help="Attempt a one-time real WeCom send")
    parser.add_argument("--send-wechat", action="store_true", help="Attempt a one-time normal WeChat send through WxPusher")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Directory for digest/debug/metrics output")
    parser.add_argument("--profiles-file", default=str(DEFAULT_PROFILE_PATH), help="Path to RSS profile YAML")
    return parser.parse_args()


def load_profile(path: Path, profile_name: str) -> RSSProfile:
    if not path.exists():
        raise SystemExit(f"RSS profile file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profiles: dict[str, Any] = data.get("profiles") or {}
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise SystemExit(f"Unknown RSS profile '{profile_name}'. Available profiles: {available}")

    raw = profiles[profile_name] or {}
    return RSSProfile(
        name=str(raw.get("name") or profile_name),
        description=str(raw.get("description") or ""),
        rss_feeds=_string_list(raw.get("rss_feeds")),
        topics=_string_list(raw.get("topics")),
        exclusions=_string_list(raw.get("exclusions")),
        max_items=max(0, int(raw.get("max_items") or 10)),
        min_score=float(raw.get("min_score") or 0),
    )


async def run_profile(args: argparse.Namespace) -> int:
    configure_logging(settings.log_level)
    profile = load_profile(Path(args.profiles_file), args.profile)
    limit = args.limit if args.limit is not None else profile.max_items
    limit = max(0, int(limit))
    fetch_limit = max(limit * 20, 500) if limit else 0

    fetcher = RSSFetcher(feed_urls=profile.rss_feeds, stop_at_limit=False)
    raw_items = await fetcher.fetch(profile.topics, fetch_limit)
    raw_debug = _items_to_debug(raw_items)

    cleaned_items = normalize_items(raw_items)
    cleaned_debug = _items_to_debug(cleaned_items)

    deduped_items = dedupe_items(cleaned_items)
    deduped_debug = _items_to_debug(deduped_items)

    ranked_items = rank_items(
        deduped_items,
        profile.topics,
        limit=max(1, len(deduped_items)),
        exclusions=profile.exclusions,
    ) if deduped_items else []
    selected_items = [item for item in ranked_items if item.score >= profile.min_score][:limit]
    selected_ids = {id(item) for item in selected_items}
    rejected_items = [item for item in ranked_items if id(item) not in selected_ids][:10]

    summary = await MockSummarizer().summarize(
        interests=profile.topics,
        items=selected_items,
        summary_length="medium",
        advanced_analysis_enabled=False,
    )
    digest = format_wecom_digest(
        User(user_id="rss_profile_test", nickname=profile.name),
        summary,
        selected_items,
    )
    empty_reason = _empty_reason(profile, fetcher.last_metrics, raw_items, cleaned_items, deduped_items, selected_items)

    wecom_send_result = await _maybe_send_wecom(args, digest)
    wechat_send_result = await _maybe_send_wechat(args, profile.name, digest)
    metrics = _build_metrics(
        profile=profile,
        feed_metrics=fetcher.last_metrics,
        raw_items=raw_items,
        cleaned_items=cleaned_items,
        deduped_items=deduped_items,
        ranked_items=ranked_items,
        selected_items=selected_items,
        rejected_items=rejected_items,
        limit=limit,
        empty_reason=empty_reason,
        send_result=wecom_send_result,
        wechat_send_result=wechat_send_result,
    )

    output_files = _save_outputs(Path(args.output), profile.name, digest, metrics, {
        "profile": _profile_to_dict(profile),
        "raw_items": raw_debug,
        "cleaned_items": cleaned_debug,
        "deduped_items": deduped_debug,
        "ranked_items": _items_to_debug(ranked_items),
        "selected_items": _items_to_debug(selected_items),
        "rejected_low_score_examples": _items_to_debug(rejected_items),
    })
    metrics["output_files"] = {key: str(path) for key, path in output_files.items()}
    output_files["metrics"].write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_report(profile, digest, metrics, output_files)
    return 0


async def _maybe_send_wecom(args: argparse.Namespace, digest: str) -> dict[str, Any]:
    reasons = []
    if not args.send_wecom:
        reasons.append("--send-wecom was not passed")
    if not settings.wecom_push_webhook_url or "replace-me" in settings.wecom_push_webhook_url:
        reasons.append("DAILY_DIGEST_WECOM_PUSH_WEBHOOK_URL is not set")
    if os.getenv("CONFIRM_WECOM_SEND") != "YES":
        reasons.append("CONFIRM_WECOM_SEND=YES is not set")

    if reasons:
        print("WeCom send skipped: " + "; ".join(reasons))
        return {"attempted": False, "sent": False, "skipped_reasons": reasons}

    print("WeCom send enabled for this one run; sending digest now.")
    sent = await WeComPushClient().send_text("rss_profile_test", digest)
    return {"attempted": True, "sent": bool(sent), "skipped_reasons": []}


async def _maybe_send_wechat(args: argparse.Namespace, profile_name: str, digest: str) -> dict[str, Any]:
    reasons = []
    if not args.send_wechat:
        reasons.append("--send-wechat was not passed")
    if os.getenv("CONFIRM_WECHAT_SEND") != "YES":
        reasons.append("CONFIRM_WECHAT_SEND=YES is not set")
    if not settings.enable_wechat_push:
        reasons.append("DAILY_DIGEST_ENABLE_WECHAT_PUSH=true is not set")
    if not settings.wxpusher_app_token or settings.wxpusher_app_token == "replace-me":
        reasons.append("DAILY_DIGEST_WXPUSHER_APP_TOKEN is not set")
    if not settings.wxpusher_uids and not settings.wxpusher_topic_ids:
        reasons.append("DAILY_DIGEST_WXPUSHER_UIDS or DAILY_DIGEST_WXPUSHER_TOPIC_IDS is not set")

    if reasons:
        print("WeChat push skipped: " + "; ".join(reasons))
        return {"attempted": False, "sent": False, "provider": settings.wechat_push_provider, "skipped_reasons": reasons}

    print("WeChat push enabled for this one run; sending through WxPusher now.")
    result = await send_wechat_push(title=f"Daily Intelligence Brief - {profile_name}", content=digest)
    print(f"WeChat push result: ok={result.ok} provider={result.provider} message={result.message}")
    return {
        "attempted": True,
        "sent": result.ok,
        "provider": result.provider,
        "status_code": result.status_code,
        "message": result.message,
        "skipped_reasons": [],
    }


def _build_metrics(
    profile: RSSProfile,
    feed_metrics: dict[str, Any],
    raw_items: list[SourceItem],
    cleaned_items: list[SourceItem],
    deduped_items: list[SourceItem],
    ranked_items: list[SourceItem],
    selected_items: list[SourceItem],
    rejected_items: list[SourceItem],
    limit: int,
    empty_reason: str | None,
    send_result: dict[str, Any],
    wechat_send_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_name": profile.name,
        "profile_description": profile.description,
        "rss_feed_count": feed_metrics.get("feed_count", len(profile.rss_feeds)),
        "feed_success_count": feed_metrics.get("feed_success_count", 0),
        "feed_failure_count": feed_metrics.get("feed_failure_count", 0),
        "raw_item_count": len(raw_items),
        "cleaned_item_count": len(cleaned_items),
        "deduped_item_count": len(deduped_items),
        "ranked_item_count": len(ranked_items),
        "final_item_count": len(selected_items),
        "limit": limit,
        "min_score": profile.min_score,
        "top_selected_items": _item_summaries(selected_items),
        "rejected_low_score_examples": _item_summaries(rejected_items),
        "empty_digest_reason": empty_reason,
        "send_result": send_result,
        "wechat_send_result": wechat_send_result,
    }


def _save_outputs(output_dir: Path, profile_name: str, digest: str, metrics: dict[str, Any], debug: dict[str, Any]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_profile = profile_name.replace("/", "_")
    paths = {
        "digest": output_dir / f"{stamp}_{safe_profile}_digest.txt",
        "debug": output_dir / f"{stamp}_{safe_profile}_debug.json",
        "metrics": output_dir / f"{stamp}_{safe_profile}_metrics.json",
    }
    paths["digest"].write_text(digest, encoding="utf-8")
    paths["debug"].write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["metrics"].write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def _print_report(profile: RSSProfile, digest: str, metrics: dict[str, Any], output_files: dict[str, Path]) -> None:
    print("\n========== RSS PROFILE TEST ==========")
    print(f"Profile: {profile.name}")
    print(f"Description: {profile.description}")
    print(f"RSS feeds: {metrics['rss_feed_count']} success={metrics['feed_success_count']} failed={metrics['feed_failure_count']}")
    print(
        "Items: "
        f"raw={metrics['raw_item_count']} cleaned={metrics['cleaned_item_count']} "
        f"deduped={metrics['deduped_item_count']} final={metrics['final_item_count']}"
    )
    if metrics["empty_digest_reason"]:
        print(f"Empty digest reason: {metrics['empty_digest_reason']}")

    print("\nTop selected items:")
    for item in metrics["top_selected_items"][:5]:
        print(f"- score={item['score']:.2f} title={item['title']}")
        print(f"  reason={item['rank_reason']}")

    print("\nRejected/low-score examples:")
    for item in metrics["rejected_low_score_examples"][:5]:
        print(f"- score={item['score']:.2f} title={item['title']}")
        print(f"  reason={item['rank_reason']}")

    print("\n========== DIGEST ==========")
    print(digest)
    print("========== OUTPUT FILES ==========")
    for label, path in output_files.items():
        print(f"{label}: {path}")


def _empty_reason(
    profile: RSSProfile,
    feed_metrics: dict[str, Any],
    raw_items: list[SourceItem],
    cleaned_items: list[SourceItem],
    deduped_items: list[SourceItem],
    selected_items: list[SourceItem],
) -> str | None:
    if selected_items:
        return None
    if not profile.rss_feeds:
        return "Profile has no RSS feeds configured."
    if feed_metrics.get("feed_success_count", 0) == 0:
        return "No RSS feeds succeeded."
    if not raw_items:
        return "Feeds succeeded, but no items matched the configured topics."
    if not cleaned_items:
        return "Raw items were missing usable title or URL after cleaning."
    if not deduped_items:
        return "All cleaned items were removed as duplicates."
    return "Items were collected but all scored below min_score."


def _item_summaries(items: list[SourceItem]) -> list[dict[str, Any]]:
    return [
        {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "source_url": item.source_url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "score": item.score,
            "matched_topics": item.matched_topics,
            "rank_reason": item.rank_reason,
        }
        for item in items
    ]


def _items_to_debug(items: list[SourceItem]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


def _profile_to_dict(profile: RSSProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "description": profile.description,
        "rss_feeds": profile.rss_feeds,
        "topics": profile.topics,
        "exclusions": profile.exclusions,
        "max_items": profile.max_items,
        "min_score": profile.min_score,
    }


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item).strip() for item in value if str(item).strip()]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_profile(parse_args())))
