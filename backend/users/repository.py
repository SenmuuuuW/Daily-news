import json
import sqlite3
from datetime import datetime, timezone

from storage.db import get_connection
from users.models import User


class UserRepository:
    def get(self, user_id: str) -> User | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None

    def upsert(self, user: User) -> User:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(user.user_id)
        created_at = existing.created_at.isoformat() if existing and existing.created_at else now

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    user_id, nickname, interests, subscription_plan, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    nickname = excluded.nickname,
                    interests = excluded.interests,
                    subscription_plan = excluded.subscription_plan,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    user.user_id,
                    user.nickname,
                    json.dumps(user.interests, ensure_ascii=False),
                    user.subscription_plan,
                    1 if user.enabled else 0,
                    created_at,
                    now,
                ),
            )
        return self.get(user.user_id) or user

    def list_active(self) -> list[User]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM users WHERE enabled = 1").fetchall()
        return [_row_to_user(row) for row in rows]

    def set_enabled(self, user_id: str, enabled: bool) -> User | None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET enabled = ?, updated_at = ? WHERE user_id = ?",
                (1 if enabled else 0, now, user_id),
            )
        return self.get(user_id)


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        user_id=row["user_id"],
        nickname=row["nickname"],
        interests=json.loads(row["interests"] or "[]"),
        subscription_plan=row["subscription_plan"],
        enabled=bool(row["enabled"]),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value) if value else None
