# Daily WeCom Digest Bot

Backend MVP for an Enterprise WeChat daily digest system. It receives WeCom messages, stores user interests, collects matching information every morning, summarizes it, formats a mobile-friendly text digest, and pushes it back through Enterprise WeChat.

This repository intentionally contains no website, dashboard, login system, payment, Kubernetes, Docker setup, microservices, or agent framework.

## Current Test Version: RSS-first Daily Digest MVP

This version focuses on making the current Daily WeCom Digest MVP usable with RSS as the main information source. It:

- reads RSS feeds from environment configuration
- filters feed entries by user interests/topics when topics are configured
- collects general RSS items when no topics are configured
- cleans and deduplicates RSS items
- ranks relevant items with deterministic rules
- summarizes RSS entries into a mobile-friendly digest
- optionally pushes the digest to Enterprise WeChat
- logs digest runs, RSS collection counts, ranking counts, and push status

## What Changed In This Version

- Improved RSS feed parsing from `DAILY_DIGEST_RSS_FEEDS`.
- Added RSS config examples for JSON arrays and comma-separated URLs.
- Added safer handling for bad or unreachable feeds.
- Improved RSS item normalization and feed metadata.
- Improved deduplication by normalized URL, normalized title, and simple title similarity.
- Improved deterministic ranking using topic matches, recency, source hints, and summary quality.
- Cleaned up the Enterprise WeChat report format.
- Added clearer logging for RSS collection, dedupe, ranking, and push attempts.
- Added safer WeCom response validation for JSON responses with `errcode`.
- Added `.env.example` and a local RSS digest helper.

## Current Limitations

- RSS is the main source for now.
- There is no full customer/bot admin system yet.
- There is no customer login.
- Payment is not implemented.
- The app does not use risky scraping or login-protected sources.
- Summaries are deterministic/simple unless an LLM integration is added later.
- Manual review may still be needed before enabling automatic customer-facing sends.

## Architecture

The backend is a modular FastAPI application with SQLite storage:

- `api/`: health check and Enterprise WeChat webhook callbacks.
- `users/`: user model, repository, and service layer.
- `plans/`: free, plus, and pro plan configuration.
- `sources/`: RSS-first fetchers plus GitHub, arXiv, and future news/API fetcher modules.
- `pipeline/`: collection, cleaning, deduplication, ranking, summarization, and WeCom formatting.
- `push/`: Enterprise WeChat text push client.
- `scheduler/`: daily digest job that can run under APScheduler or cron.
- `storage/`: SQLite schema, DB setup, plan cache, and digest logs.
- `utils/`: logging, HTTP, and small helpers.

## Data Flow

Enterprise WeChat User

-> Receive Message

-> User Management

-> Scheduler at 09:00

-> Load Active Users

-> Fetch Information

-> Clean and Deduplicate

-> Rank

-> Summarize

-> Format

-> Push To Enterprise WeChat

-> Save Logs

## Run Locally

Install dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Initialize SQLite:

```bash
python -m storage.db
```

Start the webhook server:

```bash
uvicorn main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Test receiving a user topic:

```bash
curl -X POST http://localhost:8000/api/webhook/wecom \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_user","nickname":"Test User","text":"AI, computer science"}'
```

Run the digest job once:

```bash
cd backend
python -m scheduler.daily_job
```

Seed a local test user and run an RSS digest in one command:

```bash
cd backend
DAILY_DIGEST_TEST_TOPICS="AI, security" python -m scripts.test_rss_digest
```

If no Enterprise WeChat push webhook is configured, the generated message is printed to the console and logged as a mock success. This keeps the MVP runnable without external integrations.

## Configuration

Configuration is read from environment variables with the `DAILY_DIGEST_` prefix. Useful values:

```bash
DAILY_DIGEST_DATABASE_URL=sqlite:///./daily_digest.db
DAILY_DIGEST_WECOM_INCOMING_TOKEN=replace-me
DAILY_DIGEST_WECOM_PUSH_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=replace-me
DAILY_DIGEST_DIGEST_HOUR=9
DAILY_DIGEST_DIGEST_MINUTE=0
DAILY_DIGEST_TIMEZONE=Asia/Shanghai
DAILY_DIGEST_RSS_FEEDS='["https://example.com/rss.xml"]'
```

Copy `.env.example` to `.env` for local development and adjust the feed list:

```bash
cp .env.example .env
```

For RSS, set `DAILY_DIGEST_RSS_FEEDS` as either a JSON array string:

```bash
DAILY_DIGEST_RSS_FEEDS='["https://example.com/rss.xml","https://example.com/feed"]'
```

or a comma-separated list:

```bash
DAILY_DIGEST_RSS_FEEDS=https://example.com/rss.xml,https://example.com/feed
```

If the value cannot be parsed, the app logs a warning and uses an empty feed list instead of crashing. If no RSS feed is configured at all, the local MVP uses a public default feed so the daily job can still be tested.

## Real RSS Testing

Use the profile runner to test real public RSS sources without sending to Enterprise WeChat by default:

```bash
cd backend
python -m scripts.run_rss_profile --profile ai_tech
python -m scripts.run_rss_profile --profile law_policy
python -m scripts.run_rss_profile --profile target_vertical
```

Optional arguments:

```bash
python -m scripts.run_rss_profile --profile ai_tech --limit 10
python -m scripts.run_rss_profile --profile ai_tech --output outputs/rss_tests
```

Outputs are saved under:

```text
outputs/rss_tests/
```

Each run writes:

- a digest text file
- a debug JSON file with raw, cleaned, deduped, ranked, selected, and rejected/low-score items
- a metrics JSON file with feed success/failure counts, item counts, selected items, ranking reasons, and send status

The built-in profile file is:

```text
backend/config_profiles/rss_test_profiles.yaml
```

The sample feeds are public RSS examples only. Review source terms, copyright rules, commercial permissions, and customer-specific risk before using any source in production.

## Topic and Ranking Tuning

Edit `backend/config_profiles/rss_test_profiles.yaml` to tune each profile:

- `rss_feeds`: add or remove authorized public RSS feeds
- `topics`: add keywords or phrases that should increase relevance
- `exclusions`: add terms that should push irrelevant items down
- `max_items`: control digest size
- `min_score`: raise this to make selection stricter, lower it to inspect more borderline items

Inspect `rank_reason` in the debug JSON to understand why each item was selected or rejected. A good digest should have selected items whose titles/summaries clearly match the profile topics, have understandable ranking reasons, and link back to reliable public source pages.

## Safe WeCom Send Test

Dry run, no WeCom send:

```bash
cd backend
python -m scripts.run_rss_profile --profile ai_tech
```

One-time real send test:

```bash
cd backend
CONFIRM_WECOM_SEND=YES python -m scripts.run_rss_profile --profile ai_tech --send-wecom
```

Enterprise WeChat will not send unless all of these are true:

- `--send-wecom` is passed
- `CONFIRM_WECOM_SEND=YES` is set
- `DAILY_DIGEST_WECOM_PUSH_WEBHOOK_URL` is set in `.env` or the environment

The webhook URL should stay in `.env` or your shell environment and must not be committed. The app never prints the full webhook URL.

## Normal WeChat Push With WxPusher

Enterprise WeChat webhook delivery sends messages to Enterprise WeChat groups. For this MVP, WxPusher is the first supported option for sending test RSS digests to normal WeChat users.

Before testing, the receiving users may need to scan, subscribe, or follow your WxPusher app/channel so you can obtain UIDs or topic IDs. This is for controlled testing only. A long-term official WeChat account or service account integration can be considered later.

Example `.env` values:

```bash
DAILY_DIGEST_WECHAT_PUSH_PROVIDER=wxpusher
DAILY_DIGEST_ENABLE_WECHAT_PUSH=false
DAILY_DIGEST_WXPUSHER_APP_TOKEN=replace-me
DAILY_DIGEST_WXPUSHER_UIDS=uid1,uid2
DAILY_DIGEST_WXPUSHER_TOPIC_IDS=
```

Dry run, no normal WeChat push:

```bash
cd backend
python -m scripts.run_rss_profile --profile ai_tech
```

Safe one-time normal WeChat push through WxPusher:

```bash
cd backend
CONFIRM_WECHAT_SEND=YES DAILY_DIGEST_ENABLE_WECHAT_PUSH=true python -m scripts.run_rss_profile --profile ai_tech --send-wechat
```

It will not send unless all of these are true:

- `--send-wechat` is passed
- `CONFIRM_WECHAT_SEND=YES` is set
- `DAILY_DIGEST_ENABLE_WECHAT_PUSH=true` is set
- `DAILY_DIGEST_WXPUSHER_APP_TOKEN` is configured
- at least one `DAILY_DIGEST_WXPUSHER_UIDS` or `DAILY_DIGEST_WXPUSHER_TOPIC_IDS` value is configured

Keep the WxPusher app token in `.env` or your shell environment. Do not commit real tokens, UIDs, topic IDs, or generated digest outputs.

## Enterprise WeChat Webhook

Point the Enterprise WeChat callback URL at:

```text
POST /api/webhook/wecom
```

The MVP accepts common JSON fields:

- User id: `FromUserName`, `from_user`, `user_id`, or `userid`
- Nickname: `nickname`, `user_name`, or `name`
- Message content: `Content`, `content`, `text`, or `message`

Users can send comma-separated or newline-separated topics. The webhook stores them as interests.

For outgoing messages, configure `DAILY_DIGEST_WECOM_PUSH_WEBHOOK_URL`. The push layer currently supports text messages.
If this value is empty or contains `replace-me`, the sender prints the digest locally instead of crashing.

## Plans

Plans are YAML files under `backend/plans/`:

- `free.yaml`
- `plus.yaml`
- `pro.yaml`

Each plan controls:

- maximum interest topics
- collected item count
- summary length
- whether advanced analysis is enabled

Payment is not implemented.

## Adding A Future Frontend

A React or Vue frontend can call backend APIs without changing the core backend architecture. Recommended next API additions:

- `GET /api/users/{user_id}`
- `PUT /api/users/{user_id}/interests`
- `PUT /api/users/{user_id}/enabled`
- `PUT /api/users/{user_id}/plan`

Keep frontend concerns outside the pipeline, push, and storage modules so the daily digest workflow remains independent.
