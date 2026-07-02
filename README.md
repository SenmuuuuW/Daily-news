# Daily WeCom Digest Bot

Backend MVP for an Enterprise WeChat daily digest system. It receives WeCom messages, stores user interests, collects matching information every morning, summarizes it, formats a mobile-friendly text digest, and pushes it back through Enterprise WeChat.

This repository intentionally contains no website, dashboard, login system, payment, Kubernetes, Docker setup, microservices, or agent framework.

## Architecture

The backend is a modular FastAPI application with SQLite storage:

- `api/`: health check and Enterprise WeChat webhook callbacks.
- `users/`: user model, repository, and service layer.
- `plans/`: free, plus, and pro plan configuration.
- `sources/`: RSS, GitHub, arXiv, and future news/API fetchers.
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
```

For RSS, set `DAILY_DIGEST_RSS_FEEDS` using the format supported by `pydantic-settings` for list values, for example a JSON array string.
If RSS or external fetches are unavailable, the RSS layer returns safe mock items so the local daily job still completes.

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
